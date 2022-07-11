from flask import Flask, send_from_directory
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


@app.route("/func/<evalfuncname>")
def evaluation_functions(evalfuncname):
    return send_from_directory('docs', f"{evalfuncname}.md")
