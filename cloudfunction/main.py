import torch
import flask
from pytorch_pretrained_bert import BertTokenizer, BertModel, BertForMaskedLM
import os
import psutil
from google.cloud import datastore
from google.cloud import storage
import numpy
import faiss
import json
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor
process = psutil.Process(os.getpid())
print("Finished importing")
print("Memory after importing: ", process.memory_info().rss)

print("Testing Faiss", faiss.Kmeans(10, 20).train(numpy.random.rand(1000, 10).astype("float32")))
# print("All directories and files:")
# for dirpath, dirnames, filenames in os.walk("/"):
#     print(dirpath, dirnames, filenames)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/home/cameronfranz/storage.json"
datastoreClient = datastore.Client("traininggpu")
storageClient = storage.Client()
bucket = storageClient.get_bucket("mlstorage-cloud")

INDEX_BLOB = "GutenBert/faissIndexALLBooksIMI16byte64subv"
INDEX_PATH = "/tmp/faissIndex"
MODEL_BLOB = "Data/bert-base-uncased.tar.gz"
MODEL_PATH = "/tmp/model.tar.gz"
METADATA_BLOB = "GutenBert/gutenberg-metadata.json"
METADATA_PATH = "/tmp/metadata.json"

print("Downloading and loading metadata")
bucket.blob(METADATA_BLOB).download_to_filename(METADATA_PATH)
rawMetadata = json.loads(open(METADATA_PATH).read())
os.remove(METADATA_PATH)
metadata = {}
requiredFields = ["Author", "Title", "Author Birth", "Author Death"]
for data in rawMetadata:
    missingFields = filter(lambda x: requiredField not in data, requiredFields)
    [data.update({missingField: "?"}) for missingField in missingFields]
    metadata.update({int(data["Num"]): data})

print("Downloading model")
bucket.blob(MODEL_BLOB).download_to_filename(MODEL_PATH)
print("Loading model")
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased", cache_dir="/tmp", do_lower_case=True)
model = BertModel.from_pretrained(MODEL_PATH)
os.remove(MODEL_PATH)

print("Downloading index")
bucket.blob(INDEX_BLOB).download_to_filename(INDEX_PATH)
print("Loading index")
# memory map is ~124mb in memory, loading full ~500mb file would lead to ~600mb in memory
index = faiss.read_index(INDEX_PATH, faiss.IO_FLAG_READ_ONLY | faiss.IO_FLAG_MMAP)

def withCORS(request, content="", status=200):
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400"
        }
        return (content, 204, headers)
    headers = {
        "Access-Control-Allow-Origin": "*"
    }
    return (content, status, headers)

def sentenceVector(sentence):
    seqLength = 20
    tokens = ["[CLS]"] + tokenizer.tokenize(sentence)[:seqLength] + ["[SEP]"]
    typeIDs = [0] * len(tokens)
    inputIDs = tokenizer.convert_tokens_to_ids(tokens)
    inputMask = [1] * len(inputIDs)
    # If batching, each encoded sentence has to have the same length
    # while len(inputIDs) < seqLength + 2:
    #     inputIDs.append(0)
    #     inputMask.append(0)
    #     typeIDs.append(0)
    model.eval()
    inputIDs = torch.tensor(inputIDs, dtype=torch.long).unsqueeze(0)
    inputMask = torch.tensor(inputMask, dtype=torch.long).unsqueeze(0)
    allEncoderLayers, _ = model(inputIDs, token_type_ids=None, attention_mask=inputMask)
    sentenceVector = torch.mean(allEncoderLayers[-2], dim=1)
    return sentenceVector

testSentence = "I'm a hungry HUNGRY hippOO"
print("Testing BERT: Sentence vector sum for \"{}\" : {}".format(testSentence, torch.sum(sentenceVector(testSentence))))
print("Current memory usage in bytes: ", process.memory_info().rss)

def getTextUnit(vectorIndex):
    query = datastoreClient.query(kind="BookTextUnit")
    query.add_filter("vectorNum", "=", vectorIndex)
    res = list(query.fetch())
    if res:
        return res[-1]
    else:
        print("Could not find vector key in database: {}".format(vectorIndex))
        return None

def hello_world(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    if request.method == "OPTIONS":
        return withCORS(request)
    elif request.method == "POST":
        request_json = request.get_json()
        if request_json and "sentence" in request_json:
            sentence =  request_json["sentence"]
            print("Processing sentence: ", sentence)
            if not sentence:
                flask.abort(400, {"msg": "Empty sentence"})
            vector = sentenceVector(sentence)
            rawTextUnitIndices = index.search(vector.detach().numpy(), 20)[1][0].tolist()
            textUnitIndices = [] #have to remove duplicates, not sure why there are duplicatesself.
            # faiss says the distances between two duplicate indexes' vectors are diff by ~0.000008 .
            for i in rawTextUnitIndices:
                if i not in textUnitIndices:
                    textUnitIndices.append(i)
            executor = ThreadPoolExecutor(len(textUnitIndices))
            textUnits = list(executor.map(getTextUnit, textUnitIndices))
            executor.shutdown()
            textUnits = list(filter(lambda x: x, textUnits))
            metadataToAdd = ["Author", "Title", "Author Birth", "Author Death"]
            for textUnit in textUnits:
                bookNum = textUnit["bookNum"]
                newMetadata = {k:metadata[bookNum][k] for k in metadataToAdd}
                textUnit.update(newMetadata)
            content = jsonify({"textUnits": textUnits})
            return withCORS(request, content, 200)
        else:
            content = jsonify({"msg": "Request JSON missing"})
            return withCORS(request, content, 400)
    else:
        content = jsonify({"msg": "Invalid request method"})
        return withCORS(request, content, 400)
