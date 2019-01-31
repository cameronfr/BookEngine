import torch
import flask
from pytorch_pretrained_bert import BertTokenizer, BertModel, BertForMaskedLM
from urllib.request import urlretrieve
import os
from google.cloud import datastore
from google.cloud import storage
import numpy
import faiss
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor
print("Finished importing")

print("Testing Faiss", faiss.Kmeans(10, 20).train(numpy.random.rand(1000, 10).astype("float32")))
# print("All directories and files:")
# for dirpath, dirnames, filenames in os.walk("/"):
#     print(dirpath, dirnames, filenames)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/home/cameronfranz/storage.json"
datastoreClient = datastore.Client("traininggpu")
storageClient = storage.Client()
bucket = storageClient.get_bucket("mlstorage-cloud")

# Might want to switch to using google cloud storage python library, so can make these files in bucket private.
INDEX_URL = "https://storage.googleapis.com/mlstorage-cloud/GutenBert/faissIndexFirst2000IMI16byte64subv"
INDEX_BLOB = "GutenBert/faissIndexFirst500BooksIMI16byte64subv"
INDEX_PATH = "/tmp/faissIndex"
MODEL_URL = "https://storage.googleapis.com/mlstorage-cloud/Data/bert-base-uncased.tar.gz"
MODEL_BLOB = "Data/bert-base-uncased.tar.gz"
MODEL_PATH = "/tmp/model.tar.gz"

print("Downloading model")
# print(urlretrieve(MODEL_URL, MODEL_PATH))
list(bucket.list_blobs(prefix="Data/bert"))
print(bucket.blob(MODEL_BLOB).download_to_filename(MODEL_PATH))

print("Loading model")
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased", cache_dir="/tmp", do_lower_case=True)
model = BertModel.from_pretrained(MODEL_PATH)
os.remove(MODEL_PATH)

print("Downloading index")
# print(urlretrieve(INDEX_URL, INDEX_PATH))
print(bucket.blob(INDEX_BLOB).download_to_filename(INDEX_PATH))

print("Loading index")
index = faiss.read_index(INDEX_PATH)
# index = faiss.read_index(INDEX_PATH, faiss.IO_FLAG_MMAP | faiss.IO_FLAG_READ_ONLY)
# delete downloaded index. unless MMAP (memory map) setting is faster.

def withCORS(request, content=""):
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600"
        }
        return (content, 204, headers)
    headers = {
        "Access-Control-Allow-Origin": "*"
    }
    return (content, 200, headers)

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

def f(x):
    if x>10:
        return x*x

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
        withCORS(request)
    else if request.method == "POST"
        request_json = request.get_json()
        if request_json and "sentence" in request_json:
            sentence =  request_json["sentence"]
            print("Processing sentence: ", sentence)
            if not sentence:
                flask.abort(400, {"msg": "Empty sentence"})
            vector = sentenceVector(sentence)
            textUnitIndices = index.search(vector.detach().numpy(), 15)[1][0].tolist()
            executor = ThreadPoolExecutor(len(textUnitIndices))
            textUnits = list(executor.map(getTextUnit, textUnitIndices))
            executor.shutdown()
            textUnits = list(filter(lambda x: x, textUnits))
            textUnits = list(map(lambda x: x["textUnit"], textUnits))
            content = jsonify({"textUnits": textUnits})
            withCORS(request, content)
        else:
            flask.abort(400, {"msg": "Request JSON missing"})
    else:
        flask.abort(400, {"msg": "Invalid request method"})
