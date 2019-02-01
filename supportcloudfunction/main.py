from google.cloud import datastore
from google.cloud import storage
from flask import jsonify
from concurrent.futures import ThreadPoolExecutor
import os
print("Finished importing")

datastoreClient = datastore.Client("traininggpu")
storageClient = storage.Client()
bucket = storageClient.get_bucket("mlstorage-cloud")
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/home/cameronfranz/storage.json"

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

def getTextUnit(bookNum, inBookLocation):
    query = datastoreClient.query(kind="BookTextUnit")
    query.add_filter("inBookLocation", "=", inBookLocation)
    query.add_filter("bookNum", "=", bookNum)
    res = list(query.fetch())
    res = res[0]["textUnit"] if res else None
    return res

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
        try:
            # request_json={"bookNum":1, "inBookLocations":list(range(10,70))}
            bookNum, inBookLocations = (request_json[key] for key in ["bookNum", "inBookLocations"])
            numUnitsRequested = len(inBookLocations)
            if numUnitsRequested > 25:
                raise Exception("Requested range too large")
            executor = ThreadPoolExecutor(25)
            textUnits = executor.map(getTextUnit, [bookNum]*numUnitsRequested, inBookLocations)
            textUnits = list(filter(lambda x: x, textUnits))
            executor.shutdown()
            content = jsonify({"textUnits": textUnits})
            return withCORS(request, content, 200)
        except Exception as e:
            print("Exception while processing request, ", str(e))
            content = jsonify({"msg": str(e)})
            return withCORS(request, content, 400)
    else:
        content = jsonify({"msg": "Invalid request method"})
        return withCORS(request, content, 400)
