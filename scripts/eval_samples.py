#!/usr/bin/env python3

import os
import sys
import subprocess
import json

#colors
GREEN = "\033[0;32m"
RED = "\033[0;31m"
ORANGE = "\033[0;33m"
NO_COLOR = "\033[0m"


print("")

cwd = os.getcwd()
arguments = list(sys.argv)
sample_file_path = cwd + "/" + arguments[1]
file_dir = cwd
json_tests = True

try:
    samples_file = open(sample_file_path + ".cpp:tests")
except FileNotFoundError:
    print(f"{RED}ERROR:{NO_COLOR} No json file found for test cases.")
    json_tests = False

if json_tests:
    samples_data = json.load(samples_file)
    samples_file.close()

    results = [0 for _ in range(len(samples_data))]
    last_out = [0 for _ in range(len(samples_data))]
results_from_files = []

def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True, shell=True, stderr=subprocess.STDOUT)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line 
    popen.stdout.close()
    # return_code = popen.wait()
    # if return_code:
    #     raise subprocess.CalledProcessError(return_code, cmd)

def eval_test(test_num):
    curr_sample = samples_data[test_num]
    input_file = open("in_temp_file", "w")
    input_file.write(curr_sample["test"])
    input_file.close()

    print(f"Test {test_num}:")
    print(curr_sample["test"])
    print("My answer: ")

    output = ""
    output_no_stderr = ""
    for line in execute(f"{sample_file_path} < in_temp_file"):
        print(line.rstrip())
        output += line.rstrip() + "\n";
        if "\033[1;31m" not in line:
            output_no_stderr += line.rstrip() + "\n"

    output = output.rstrip()
    output_no_stderr = output_no_stderr.rstrip()

    flag = False
    for answer in curr_sample["correct_answers"]:
        if answer.rstrip() == output_no_stderr:
            print("")
            print(f"[VERDICT: {GREEN}AC{NO_COLOR}]")
            flag = True
            results[test_num] = "AC"
            break
    if not flag:
        print("")
        print("Sample answer: ")
        if len(curr_sample["correct_answers"]) > 0:
            print(curr_sample["correct_answers"][0])
        else:
            print(f"{ORANGE}There are no correct answers in json file{NO_COLOR}")
        print("")
        print(f"[VERDICT: {RED}WA{NO_COLOR}]")
        results[test_num] = "WA"
    last_out[test_num] = output_no_stderr

    print("--------------\n")

def eval_test_from_file(test_num):
    in_file = open(f"./in{test_num}.txt", "r")
    print(f"Test from file number {test_num}:")
    lines = in_file.readlines()
    for line in lines:
        print(line, end = "");
    print("\nMy answer: ")

    output = ""
    output_no_stderr = ""
    for line in execute(f"{sample_file_path} < ./in{test_num}.txt"):
        print(line.rstrip())
        output += line.rstrip() + "\n";
        if "\033[1;31m" not in line:
            output_no_stderr += line.rstrip() + "\n"

    output = output.rstrip()
    output_no_stderr = output_no_stderr.rstrip()

    try:
        ans_file = open(f"./ans{test_num}.txt", "r")
        out_lines = ans_file.readlines()
        correct_ans = ""
        for line in out_lines:
            correct_ans += line.rstrip() + "\n";
        correct_ans = correct_ans.rstrip()

        if output_no_stderr == correct_ans:
            print("")
            print(f"[VERDICT: {GREEN}AC{NO_COLOR}]")
            found = False
            for i in range(len(results_from_files)):
                if results_from_files[i][0] == test_num:
                    results_from_files[i][1] = "AC"
                    found = True
                    break
            if not found:
                results_from_files.append([test_num, "AC"])
        else:
            print("")
            print("Sample answer: ")
            print(correct_ans)
            print("")
            print(f"[VERDICT: {RED}WA{NO_COLOR}]")
            found = False
            for i in range(len(results_from_files)):
                if results_from_files[i][0] == test_num:
                    results_from_files[i][1] = "WA"
                    found = True
                    break
            if not found:
                results_from_files.append([test_num, "WA"])

    except FileNotFoundError:
        print("")
        print("Sample answer: ")
        print(f"{ORANGE}Could not find sample answer file{NO_COLOR}")
        print("")
        print(f"[VERDICT: {RED}WA{NO_COLOR}]")
        found = False
        for i in range(len(results_from_files)):
            if results_from_files[i][0] == test_num:
                results_from_files[i][1] = "WA"
                found = True
                break
        if not found:
            results_from_files.append([test_num, "WA"])

    print("--------------\n")

def read_test():
    print("Input the test case and press Ctrl-D to save it.")
    test_str = ""
    while True:
        try:
            line = input()
        except EOFError:
            break
        test_str += line + "\n"
    return test_str

def accept_test(test_num):
    if last_out[test_num] not in samples_data[test_num]["correct_answers"]:
        samples_data[test_num]["correct_answers"].append(last_out[test_num])
        json_file = open(sample_file_path + ".cpp:tests", "w")
        json.dump(samples_data, json_file)
        json_file.close()
    eval_test(test_num)

def display_answers(test_num):
    if len(samples_data[test_num]["correct_answers"]) == 0:
        print(f"{ORANGE}There are no correct answers in json file{NO_COLOR}")
    else:
        cn = 0
        print("Correct answers:")
        for answer in samples_data[test_num]["correct_answers"]:
            print(f"Answer {cn}:")
            print(answer)
            print("")
            cn += 1

def wa_test(test_num):
    if last_out[test_num] in samples_data[test_num]["correct_answers"]:
        samples_data[test_num]["correct_answers"].remove(last_out[test_num])
        json_file = open(sample_file_path + ".cpp:tests", "w")
        json.dump(samples_data, json_file)
        json_file.close()
    eval_test(test_num)

def add_test():
    test_str = read_test()
    test_dict = {
        "correct_answers": [],
        "test" : test_str
    }
    samples_data.append(test_dict)
    json_file = open(sample_file_path + ".cpp:tests", "w")
    json.dump(samples_data, json_file)
    json_file.close()
    results.append(0)
    last_out.append(0)

def help():
    help_str = """
    List of available commands for test case evaluator:

    - help: Display the list of available commands.
    - new: Add a new test to the json file.
    - run #test_num: Run the test with index "test_num". If "test_num" is -1, all tests will be executed.
    - quit: Exit interactive console. Alias: q.
    - ac #test_num: Mark the last output for test with index "test_num" as correct.
    - wa #test_num: Mark the last output for test with index "test_mum" as incorrect.
    - numtests: Print the number of tests.
    - dpans #test_num: Show saved correct answers for test with index "test_num".
    - del #test_num: Delete test with index "test_num".
    """

    print(help_str)

def delete(test_num):
    samples_data.pop(test_num)
    json_file = open(sample_file_path + ".cpp:tests", "w")
    json.dump(samples_data, json_file)
    json_file.close()
    results.pop(test_num)
    last_out.pop(test_num)

def run_all():
    if json_tests:
        for i in range(len(samples_data)):
            eval_test(i)

    files = False
    for i in range(1, 51):
        if os.path.exists(f"./in{i}.txt"):
            eval_test_from_file(i);
            files = True

    print("Summary:")
    if json_tests:
        print("Tests from json file:")
        for i in range(len(results)):
            if results[i] == "AC":
                print(f"    Test {i}: {GREEN}AC{NO_COLOR}")
            else:
                print(f"    Test {i}: {RED}WA{NO_COLOR}")

    if files:
        print("Tests from txt files:")
        for result in results_from_files:
            if result[1] == "AC":
                print(f"    Test {result[0]}: {GREEN}AC{NO_COLOR}")
            else:
                print(f"    Test {result[0]}: {RED}WA{NO_COLOR}")

    print("")

run_all()

print("Test Case Evaluator Console (type \"quit\" to exit)")
while True:
    command = input(">>> ").split()
    if command[0].lower() == "quit" or command[0].lower() == "q":
        break

    elif command[0].lower() == "run":
        if (int(command[1]) == -1):
            run_all()

    elif command[0].lower() == "ac":
        if (int(command[1]) == -1):
            for i in range(len(samples_data)):
                accept_test(i)
                eval_test(i)

            print("Summary:")
            for i in range(len(results)):
                if results[i] == "AC":
                    print(f"Test {i}: {GREEN}AC{NO_COLOR}")
                else:
                    print(f"Test {i}: {RED}WA{NO_COLOR}")
            print("")
        else:
            accept_test(int(command[1]))

    elif command[0].lower() == "dpans":
        display_answers(int(command[1]))

    elif command[0].lower() == "wa":
        wa_test(int(command[1]))

    elif command[0].lower() == "new":
        add_test()

    elif command[0].lower() == "numtests":
        print(f"Number of tests: {len(samples_data)}")

    elif command[0].lower() == "help":
        help()

    elif command[0].lower() == "del":
        delete(int(command[1]))
