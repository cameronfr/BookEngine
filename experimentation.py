#Start bert-as-a-service with [bert-serving-start -model_dir ../../Bert_Uncased_Base_En/ -num_worker=4 -max_seq_len=200] -- really nice.
#V100: 120,000 paragaphs, max_seq_len 200, (3 workers on BAAS but 100% utilization anyways) -> 250 samples / second.
#MBP CPU: Using all 8 cores (one worker, 100% utliziation), max_seq_len 200, dummy sentence -> 2.4 samples / second. So seems possible to run even on small servers.
#If want all processing to be done in one day on one V100, can have max 21million samples of length 200.
#Remove duplicate books (should be 40,000, not 70,000) and improve paragraph selection.
#Now using nice dataset from https://github.com/aparrish/gutenberg-dammit. Was using dataset from gutenberg-tar.com of .txt files.
#Should switch to Bert_Multilingual_Cased, as it can parse multiple languages and doesn't strip down to ascii.

import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
from scipy.misc import imresize
from torch import nn
from torch import optim
from google.cloud import storage
import os
import io
import re
from bert_serving.client import BertClient
from itertools import chain

%matplotlib inline
plt.style.use("ggplot")
%config InlineBackend.figure_format = 'svg'
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)

def processBook(book):
    bookText = book.read()
    header = re.match("[\S\s]*\*\*\* START OF THIS .*\*\*\*", bookText)
    if header:
        header = header.group(0)
        title = re.match("[\S\s]*Title: (.*)", header).groups(1)[0]
        author = re.match("[\S\s]*Author: (.*)", header).groups(1)[0]
    else:
        print(book)
    # book = re.sub("[\S\s]*\*\*\* START OF THIS .*\*\*\*", "", book) #too slow for big books, just find the line
    # book = re.sub("([\S\s]*)(\*\*\* END OF THIS .*\*\*\*[\S\s]*)", r"\1", book)

    paragraphs = list(map(lambda s: s.replace("\n", " ").strip(), bookText.split("\n\n"))) #how to split into meaningful bits of content better?
    paragraphs = list(filter(lambda p: p != "" and (len(p.split()) > 50), paragraphs))
    bookParagraphList.append(paragraphs)

book = open("frankenstein.txt", encoding="utf8", errors="ignore")

numBooks = 0
bookParagraphList = []
allFileNames = []
for dirpath, dirnames, filenames in os.walk("/home/cameronfranz/BookEngine/Books/books/gutenberg/6/0"):
    for file in filenames:
        if not file.endswith(".txt"):
            continue
        if (file.split(".txt")[0] + "-8.txt") in filenames:
            continue
        processBook(open(os.path.join(dirpath, file), encoding="utf8", errors="ignore"))
        allFileNames.append(file)
        numBooks += 1

len(bookParagraphList)
numBooks
allFileNames



paragraphs = list(chain(*bookParagraphList))
len(paragraphs)
bc = BertClient()
bc.encode(["I went to the beach to frolick in the sand and search for sea shells. I haven't had such a great time in years."]*100)
allVecs = bc.encode(paragraphs)
allVecs.shape
allVecs = allVecs / np.sqrt(np.sum(allVecs * allVecs, axis=1)).reshape(-1, 1)
print(paragraphs[np.argmax(np.matmul(allVecs, bc.encode(["Walking through the forest"]).transpose()))])
paragraphs[100]


cosDist = lambda u,v: np.dot(u, v) / (np.linalg.norm(u)*np.linalg.norm(v))
cosDist(u, v)
