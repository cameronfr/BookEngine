#Start bert-as-a-service with [bert-serving-start -model_dir ../../Bert_Uncased_Base_En/ -num_worker=4 -max_seq_len=200] -- really nice.
#V100: 120,000 paragaphs, max_seq_len 200, (3 workers on BAAS but 100% utilization anyways) -> 250 samples / second.
#MBP CPU: Using all 8 cores (one worker, 100% utliziation), max_seq_len 200, dummy sentence -> 2.4 samples / second. So seems possible to run even on small servers.
#If want all processing to be done in one day on one V100, can have max 21million samples of length 200.
#Remove duplicate books (should be 40,000, not 70,000) and improve paragraph selection.
#Now using nice dataset from https://github.com/aparrish/gutenberg-dammit. Was using dataset from gutenberg-tar.com of .txt files.
#Should switch to Bert_Multilingual_Cased, as it can parse multiple languages and doesn't strip down to ascii.
#Stats: 50,729 books and 17,396,418 paragraphs over 50 words => avg 343 paragraphs over 50 words per book.
#As long as max_seq_len captures whole of text, the vectors will be the same, even if max_seq_len differs.
#Is Bert applied to a paragraph different from the average of bert applied to each sentence in the paragraph?
import torch
import time
import numpy as np
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
from scipy.misc import imresize
from torch import nn
from torch import optim
from google.cloud import storage
import os
import io
import json
from bert_serving.client import BertClient
from itertools import chain
from google.cloud import datastore
from google.cloud import storage
import pickle
import math
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
import tqdm
# root = logging.getLogger()
# root.addHandler(logging.StreamHandler(os.fdopen(1, "w")))
# logging.warning("Logging test")
from google.cloud import logging
loggingClient = logging.Client()
logger = loggingClient.logger("v100processor")
logger.log_text("Cloud logging test")  # API call

%matplotlib inline
plt.style.use("ggplot")
%config InlineBackend.figure_format = 'svg'
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)

os.environ['GOOGLE_APPLICATION_CREDENTIALS']="/home/cameronfranz/storage.json"
bertClient = BertClient()
rootPath = "/home/cameronfranz/BookEngine/BooksGBDamn/gutenberg-dammit-files/"
metadata = json.loads(open(os.path.join(rootPath, "gutenberg-metadata.json")).read())
datastoreClient = datastore.Client("traininggpu")

def processBook(bookPath, bookFilename):
    with open(bookPath, encoding="utf8", errors="ignore") as f:
        bookText = f.read()
    bookNumber = int(bookFilename.split(".")[0])
    # paragraphs = list(map(lambda s: s.replace("\n", " ").strip(), bookText.split("."))) #how to split into meaningful bits of content better?
    # paragraphs = list(filter(lambda p: p != "" and (len(p.split()) > 7), paragraphs))
    paragraphs = list(map(lambda s: s.replace("\n", " ").strip(), bookText.split("\n\n"))) #how to split into meaningful bits of content better?
    return {"bookNum": bookNumber, "textUnits": paragraphs}

# Traverse directory and get each book
def loadAllBooks(subdir = ""):
    numBooks = 0
    bookDicts = []
    processFunctions = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(rootPath, subdir)):
        dirnames.sort()
        filenames.sort()
        futures = []
        for filename in filenames:
            if not filename.endswith(".txt"):
                continue
            processFunctions.append(lambda dirpath=dirpath, filename=filename: processBook(os.path.join(str(dirpath), str(filename)), str(filename)))
            numBooks += 1
    executor = ThreadPoolExecutor(max_workers=200)
    futures = [executor.submit(f) for f in processFunctions]
    bookDicts += [f.result() for f in futures]
    executor.shutdown()
    print("Loaded {} books".format(len(bookDicts)))
    return bookDicts

def put_multi(dbObjects):
    # datastore.Client object is not threadsafe -- misses like 0.1% of objects.
    # use inner function to make sure items cleaned up after failure
    def upload(entities):
        with client.transaction():
            client.put_multi(entities)
    client = datastore.Client("traininggpu")
    entities = []
    failCount = 0
    for obj in dbObjects:
        key = client.key("BookTextUnit", obj["key"])
        del obj["key"]
        entity = datastore.Entity(key=key, exclude_from_indexes=['textUnit']) #next time, should make own id from bookNum+bookPos. So will avoid duplicates.
        entity.update(obj)
        entities.append(entity)
    try:
        upload(entities)
    except Exception as e:
        print("Transaction failed, {}, retrying...".format(str(e)))
        failCount += 1
        time.sleep(np.random.randint(3, 12))
        if failCount < 30:
            upload(entities)
        else:
            print("Transaction failed, {}, not retrying, {}".format(str(e), str(dbObjects)))
            raise e

def uploadDBObjects(dbObjects):
    UPLOAD_LIMIT = 500
    numDivisions = math.ceil(len(dbObjects)/UPLOAD_LIMIT)
    dataList = [dbObjects[i*UPLOAD_LIMIT:(i+1)*UPLOAD_LIMIT] for i in range(numDivisions)]
    numThreads = min(100, numDivisions) # limit threads. I think datastore might create one FD per obj, so set ulimit -n more than 500*100 = 50000
    executor = ThreadPoolExecutor(max_workers=numThreads)
    futures = [executor.submit(put_multi, data) for data in dataList]
    return (executor, futures)

((11507*5000)/100000)*0.18 #cost to put all book paragraphs in DB

bookDicts = loadAllBooks("")
# Convert book to corresponding vectors and database objects, update database every 500 books
# State of this loading: vectorLists, globalVectorNum, bookNumber/batch
# vectorLists = []
# vectorLists = pickle.load(open("vectorLists", "rb"))
(startBook, globalVectorNum) = pickle.load(open("progressState", "rb"))
print("Starting at book {} and vector num {}".format(startBook, globalVectorNum))
dbObjectsBuffer = []
vectorBuffer = []
for idx, bookDict in enumerate(bookDicts[startBook:]):
    currentBookIdx = startBook + idx
    textUnits = bookDict["textUnits"]
    shouldBeVectored = lambda u: (u != "") and (len(u.split()) > 50)
    vectoredTextUnitsMap = list(map(shouldBeVectored, textUnits))
    vectors = list(filter(shouldBeVectored, textUnits))
    if vectors:
        vectorBuffer += vectors

        for jdx, textUnit in enumerate(textUnits):
            key = "bookNo" + str(bookDict["bookNum"]) + "pos" + str(jdx)
            dbObj = {"key": key, "bookNum": bookDict["bookNum"], "textUnit": textUnit, "inBookLocation": jdx}
            if vectoredTextUnitsMap[jdx]:
                dbObj["vectorNum"] = globalVectorNum
                globalVectorNum += 1
            dbObjectsBuffer.append(dbObj)
    if ((idx+1) % 500 == 0) or ((currentBookIdx+1) == len(bookDicts)):
        def logMsg(x):
            logger.log_text(x)
            print(x)

        logMsg("Starting upload of latest book textUnits ({} of them) to database, up to book {}, globalVecNum {}".format(len(dbObjectsBuffer), currentBookIdx+1, globalVectorNum))
        uploadManager = uploadDBObjects(dbObjectsBuffer) #can make this async without issue, I think.
        dbObjectsBuffer = []

        logMsg("Converting textUnits to vectors({} of them), up to book {}, globalVecNum {}".format(len(vectorBuffer), currentBookIdx+1, globalVectorNum))
        encodedVectors= bertClient.encode(vectorBuffer)
        vectorBuffer = []

        logMsg("Saving vector buffer to disk")
        fileObject = open("vectorListPt{}".format(currentBookIdx+1), 'wb')
        pickle.dump(encodedVectors, fileObject)
        fileObject.close()

        logMsg("Waiting for upload to finish")
        [f.result() for f in uploadManager[1]] # make sure any errors are thrown in main thread
        uploadManager[0].shutdown(wait=True)

        # print("Updating latest book vectors to index, up to book ", idx)
        # index.add(list(chain(*bookVectorLists)))
        # bookVectorLists = []
        logMsg("Saving progress state to file")
        fileObject = open("progressState", 'wb')
        pickle.dump((currentBookIdx+1, globalVectorNum), fileObject)
        fileObject.close()

        logMsg("Finished updating database and index, up to book {}, globalVecNum {}".format(currentBookIdx+1, globalVectorNum))

#------------------------------ VERIFYING AND STUFF ------------------------------#
print("test")
bookVectorLists = vectorLists
len(vectorBuffer)
len(bookVectorLists)
len(dbObjectsBuffer)
num = 0
for i in dbObjectsBuffer:
    if "vectorNum" in i:
        assert i["vectorNum"] == num
        num += 1
num
len(list(filter(lambda x: "vectorNum" in x, dbObjects)))
dbObjects[10]["vectorNum"]
%who

globalVectorNum
query = datastoreClient.query(kind="BookTextUnit")
query.add_filter("vectorNum", ">", 5772007)
query.add_filter("vectorNum", ">", 5702007)
query.add_filter("vectorNum", "=", 4953237)
bookDicts[25000]["bookNum"]
bookDicts[25500]["bookNum"]
query.add_filter("bookNum", ">", 26194 - 1)
query.add_filter("bookNum", "<", 26790)
query.keys_only()
allEntities = query.fetch()
list(allEntities)[0]["bookNum"]
len(list(allEntities))
num = 0
executor = ThreadPoolExecutor(100)
futures = []
for i in tqdm.tqdm(allEntities):
    x = executor.submit(lambda key=i.key: datastoreClient.delete(key))
    futures.append(x)
    num += 1
len(dbObjectsBuffer)
[f for f in futures[380000:]]
len(dbObjectsBuffer) - num
executor.shutdown(wait=True)
len(dbObjectsBuffer) + len(dbObjectsBuffer) - 24932
for i in range(1000): # stress test # of file descriptions
    f = open("test" +str(i), "wb")
#------------------------------ TESTING AND SAVING TESTING STUFF ------------------------------#
print("tesT")
len(bookVectorLists)
totalLen = 0
for vec in bookVectorLists:
    totalLen += vec.shape[0]
totalLen
len(dbObjects)
globalVectorNum

fileObject = open("bookVectorListsFirst2000", 'wb')
pickle.dump(bookVectorLists, fileObject)
fileObject.close()
fileObject = open("dbObjectsFirst2000", 'wb')
pickle.dump(dbObjects, fileObject)
fileObject.close()

# Upload Database objects to google cloud
os.environ['GOOGLE_APPLICATION_CREDENTIALS']="/home/cameronfranz/storage.json"
client = datastore.Client("traininggpu")
entity = datastore.Entity(key=client.key("BookTextUnit"))
entity.update({"test": 12})
client.put(entity)

# Uploading stuff to the bucket
os.environ['GOOGLE_APPLICATION_CREDENTIALS']="/home/cameronfranz/storage.json"
storageClient = storage.Client()
list(storageClient.list_buckets())
list(storageClient.list_blobs(prefix="GutenBert/"))
bucket = storageClient.get_bucket("mlstorage-cloud")
bucket.blob("poems/poems.csv").download_to_filename("poems.csv")
bucket.blob("GutenBert/faissIndexFirst2000IMI16byte64subv").download_to_filename("faissIndex")
bucket.blob("GutenBert/faissIndexFirst500BooksIMI16byte64subv").upload_from_filename("faissIndexFirst500BooksIMI16byte64subv")

#------------------------------ BUILDING THE FAISS INDEX AND TUNING IT ------------------------------#

obj = pickle.load(open("dbObjectsFirst2000", "rb"))
for o in obj:
    if ("vectorNum" in o) and (o["vectorNum"] == 449198):
        print(o)

# Create and save FAISS index
import faiss

os.chdir("/home/cameronfranz/")
bookVectorLists = pickle.load(open("bookVectorListsFirst2000", "rb"))
globalVectorNum
allVecs = np.array(list(chain(*bookVectorLists)))
indexSlow = faiss.IndexFlatIP(768)
allVecs = allVecs / np.sqrt(np.sum(allVecs * allVecs, axis=1)).reshape(-1, 1)
indexSlow.reset()
indexSlow.add(allVecs)
indexSlow.ntotal
D, I = indexSlow.search(allVecs[100:200], 1)
faiss.write_index(indexSlow, "faissIndexSlow")
test11 = faiss.read_index("faissIndexSlow") #not sure how much memory this uses w.r.t actual size
test11 = 0
test11 = faiss.read_index("faissIndexSlow", faiss.IO_FLAG_MMAP) #not sure how much memory this uses w.r.t actual size

# Think will use 16-byte codes because memory seems to be double the expected (expect ~25 mb, got ~50mb). Training and adding way slower for OP16 for some reason. Don't think 32byte was training correctly.
# Might just be because use not using enough vectors -- IMI with 2x13 on 10M vecs takes +80%, while 2x10 on 10M vecs takes +10%.
# index = faiss.index_factory(768, "OPQ32_128, IVF16384_HNSW32, PQ32") #need 30 to 256 times 16384 training vecs, 1M would be ~60x 16384. Takes 6min on 700k vecs, so fast.
index = faiss.index_factory(768, "OPQ16_64, IMI2x10, PQ16") #IVF above has like +112% overhead (so *2.12), this has 10% overhead
index.train(allVecs)
index.reset()
index.ntotal
index.add(allVecs)
allVecs.shape
index.is_trained
index.search(allVecs[:10], 1)[1]
faiss.write_index(index, "faissIndexFirst13000BooksIMI16byte64subv")
storageClient = storage.Client()
bucket = storageClient.get_bucket("mlstorage-cloud")
bucket.blob("GutenBert/faissIndexFirst13000BooksIMI16byte64subv").upload_from_filename("faissIndexFirst13000BooksIMI16byte64subv")

index = faiss.read_index("faissIndex") #not sure how much memory faiss.IO_FLAG_READ_ONLY uses w.r.t actual size

queries = allVecs[0:10000]
base = allVecs[10000:20000]
index.reset()
index.add(base)
indexSlow.reset()
indexSlow.add(base)
index.ntotal
indexSlow.ntotal
inTopKAccuracy = lambda k: np.sum([res[0] in res[1:6] for res in np.concatenate((indexSlow.search(queries, 1)[1], index.search(queries, k)[1]), axis=1)])/queries.shape[0]
inTopKAccuracy(1)

groundTruth = np.array([np.argmax(np.matmul(base, x), axis=0) for x in queries]).reshape((-1, 1))
crit = faiss.OneRecallAtRCriterion(queries.shape[0], 1)
crit.set_groundtruth(None, groundTruth.astype("int64"))
crit.nnn = groundTruth.shape[1] #number of nearest neighbors that crit requests.
params = faiss.ParameterSpace()
params.initialize(index)
params.n_experiments = 500 #crucial, .explore(...) won't return any operating points without this.
opi = params.explore(index, queries, crit)
opi.optimal_pts.size()
#
ops = opi.optimal_pts
n = ops.size()
plt.plot([ops.at(i).perf for i in range(n)], [(ops.at(i).t / queries.shape[0]) * 1000 for i in range(n)], marker='o') #ms per query
params.set_index_parameters(index, ops.at(14).key)

#------------------------------ EXPERIMENTATION ------------------------------#

print("Number of paragraphs: ", len(list(chain(*bookParagraphList))))
print("Number of books: ", numBooks)


paragraphs = list(chain(*bookParagraphList))[:200000]
lens = [len(p.split()) for p in paragraphs]
bc = BertClient()
np.sum(bc.encode(["I'm a hungry HUNGRY hippOO"])[0])
allVecs = bc.encode(paragraphs)
allVecs.shape
allVecs = allVecs / np.sqrt(np.sum(allVecs * allVecs, axis=1)).reshape(-1, 1)

#These don't work well, at least on first 50,000 paragraphs greater than len 50
query = "A dog playing in the sand."
query = "The cat was chasing a bird."
query = "Sleeping under the willow tree."
query = "I was cutting up the onions for a stew"
query = "We were walking through the forest on a hot summer day"
query = "I was ready for death"
query = "We are alone in the universe"
query = "The onion was ripe"

#Trying splitting by sentence (split by . for now) and seeing if this query works better. len > 10. Lets do first 200,000
maxSimList = np.argsort(np.matmul(allVecs, bc.encode([query]).transpose()), axis=0).flatten()[::-1][0:10]
maxSimList = np.argsort(np.matmul(allVecs2, bc.encode([query]).transpose()), axis=0).flatten()[::-1][0:10]
paragraphs[59447-2:59447+2]
[print(paragraphs[i]) for i in maxSimList]

cosDist = lambda u,v: np.dot(u, v) / (np.linalg.norm(u)*np.linalg.norm(v))
cosDist(u, v)
