from flask import Flask, request, redirect
import json, subprocess
import datetime
import os
import sys
import signal

filename = list(sys.argv)[1]

PORT = 12345

def createNewTask(data):
    taskData = json.loads(data.decode())

    for i in range(len(taskData["tests"])):
        taskData["tests"][i]["test"] = taskData["tests"][i].pop("input")
        taskData["tests"][i]["correct_answers"] = [taskData["tests"][i].pop("output")]

    with open(f"{filename}.cpp:tests", "w") as f:
        json.dump(taskData["tests"], f)
        print("Done creating sample tests file")
    os.kill(os.getpid(), signal.SIGINT)
    

app = Flask(__name__)

@app.route('/' , methods = ['POST'])
def getData():
    createNewTask(request.data)
    return redirect('/')

app.run(port=PORT)
