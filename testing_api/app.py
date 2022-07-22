from flask import Flask, send_from_directory, request
import os

app = Flask(__name__)


@app.route("/testingfunctions")
def testingfunctions():
    return {
        "data": {
            "admin_evaluationFunctions": {
                "edges": [{
                    "name": "symbolicEqual",
                    "url": "http://127.0.0.1:5050/func/symbolicEqual",
                }, {
                    "name": "isExactEqual",
                    "url": "http://127.0.0.1:5050/func/isExactEqual",
                }, {
                    "name": "isSimilar3",
                    "url": "http://127.0.0.1:5050/func/isSimilar3",
                }, {
                    "name": "arrayEqual",
                    "url": "http://127.0.0.1:5050/func/arrayEqual",
                }, {
                    "name": "isSimilar",
                    "url": "http://127.0.0.1:5050/func/isSimilar"
                }],
                "total":
                5
            }
        }
    }


@app.route("/partial")
def partial():
    # Check headers
    if request.headers.get('api-key') != "TESTING":
        return {
            "statusCode": 401,
            "message": "Incorrect API key",
            "error": "Unauthorized"
        }

    return {
        "edges": [{
            "name":
            "isExactEqual",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/isExactEqual"
        }, {
            "name":
            "arrayEqual",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/arrayEqual"
        }, {
            "name":
            "wolframAlphaEqual",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/wolframAlphaEqual"
        }, {
            "name":
            "symbolicEqual",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/symbolicEqual"
        }, {
            "name":
            "arraySymbolicEqual",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/arraySymbolicEqual"
        }, {
            "name":
            "isSimilar",
            "url":
            "https://c1o0u8se7b.execute-api.eu-west-2.amazonaws.com/default/isSimilar"
        }],
        "total":
        6
    }


@app.route("/func/<evalfuncname>")
def evaluation_functions(evalfuncname):
    return send_from_directory('docs', f"{evalfuncname}.md")
