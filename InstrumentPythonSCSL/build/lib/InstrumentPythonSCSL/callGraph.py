import code2flow
import json

import os

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '../'))

def generate_json(modules: list):
    # generate json
    json_file = os.path.join(ROOT_DIR, 'code2flowGraph2.json')
    print(f"call graph written in {json_file}")
    code2flow.code2flow(modules, json_file)
    return json_file


def getPath(filenames: list, function1: str, function2: str):
    # Opening JSON file
    with open(generate_json(filenames)) as json_file:
        data = json.load(json_file)
        # getting the node id from the call graph for the 2 functions
        f1 = getNodeFromFunction(file_path_to_code2flow(function1), data)
        f2 = getNodeFromFunction(file_path_to_code2flow(function2), data)
        func = []
        # try to find a path between f1 and f2 using top Down approach
        topDown_path = topDownPath(data, f1, f2)
        # if there is no path between f1 and f2
        if topDown_path == []:
            # try to find path between f1 and f2 with bottomUpApproach (by analyzing if a parent of f1 connects to f2)
            path = bottomUpPath(data, f1, f2)
        else:
            path = topDown_path

        # remove the first function from path, as when doing diagnostics we will analyze an event in f1 that may not be the first event in the function
        # path.remove(f1)

        # transform node ids into function names
        for node in path:
            func.append(file_path_from_code2flow(getFunctionFromNode(node, data)))

        # return only unique functions on the path
        return unique(func)


def getFunctionFromNode(node_id: str, data: dict):
    for node in data['graph']['nodes']:
        if node_id == node:
            return data['graph']['nodes'][node]['name']


def getNodeFromFunction(function: str, data: dict):
    for node in data['graph']['nodes']:
        if function == data['graph']['nodes'][node]['name']:
            return node


# get all children between two functions
def topDownPath(data: dict, node1: str, node2: str, path=[]):
    path = path + [node1]
    if node1 not in data['graph']['nodes'] or node2 not in data['graph']['nodes']:
        print(f"function node {file_path_from_code2flow(getFunctionFromNode(node1, data)), node1,node2} not in graph!")
        return []

    if node1 == node2:
        return path

    paths = []
    for child in getChildren(data, node1):
        if child not in path:
            newpaths = topDownPath(data, child, node2, path)
            for newpath in newpaths:
                paths.append(newpath)

    return paths


# get path between two nodes by checking if parent of node1 connects to node2
def bottomUpPath(data: dict, node1: str, node2: str, path=[]):
    path = path + [node1]
    if node1 not in data['graph']['nodes'] or node2 not in data['graph']['nodes']:
        print("function node not in graph!")
        return []

    if node1 == node2:
        return path

    paths = []
    for parent in getParents(data, node1):
        if parent not in path:
            newpaths = topDownPath(data, parent, node2, path)
            if newpaths == []:
                newpaths = bottomUpPath(data, parent, node2, path)
            for newpath in newpaths:
                paths.append(newpath)

    return paths


def getParents(data, node):
    parents = []
    for j in data['graph']['edges']:
        if j['target'] == node:
            parents.append(j["source"])

    return parents


def getChildren(data, node):
    children = []
    for j in data['graph']['edges']:
        if j['source'] == node:
            children.append(j["target"])

    return children


def file_path_to_code2flow(file_path: str):
    # remove from file path ".py" and add instead ":"
    path = file_path.replace(".py", ":")
    return path


def file_path_from_code2flow(file_path: str):
    path = file_path.replace(":", ".py", 1)
    return path



# function to get unique values
def unique(list1):
    # initialize a null list
    unique_list = []

    # traverse for all elements
    for x in list1:
        # check if exists in unique_list or not
        if x not in unique_list:
            unique_list.append(x)

    return unique_list


def get_call_graph(files: list):
    # generate json
    json_output = os.path.join(ROOT_DIR, 'code2flowGraph3.json')
    # print(f"call graph written in {json_output}")
    code2flow.code2flow(files, json_output)
    graph_nodes = []
    with open(json_output) as json_file:
        data = json.load(json_file)
        for node in data['graph']['nodes']:
            graph_nodes.append(file_path_from_code2flow(getFunctionFromNode(node, data)))
    return graph_nodes


if __name__ == "__main__":
    # filename = os.path.join(ROOT_DIR,"examples/packtest/example.py")
    # print(getPath([os.path.join(ROOT_DIR, "../examples/packtest/example.py"), os.path.join(ROOT_DIR,
    #                                                                                        "../examples/packtest/ex.py")], 'example.py:b', "ex.py:e"))
    print(get_call_graph(["ppt.py"]))
