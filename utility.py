import pymel.core as pm
import pymel.core.datatypes as dt

##########################
# Usefull function
##########################

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)


def get_node(name):
    node_list = pm.ls(name)
    node = None

    if node_list:
        node = node_list[0]

    return node


def get_matrix(obj):
    return pm.xform(obj, worldSpace=1, matrix=1, q=1)


def frange(start, stop=None, step=None):
    # if set start=0.0 and step = 1.0 if not specified
    start = float(start)

    if stop is None:
        stop = start + 0.0
        start = 0.0

    if step is None:
        step = 1.0

    # print("start = ", start, "stop = ", stop, "step = ", step)

    count = 0
    while True:
        temp = float(start + count * step)
        if step > 0 and temp >= stop:
            break
        elif step < 0 and temp <= stop:
            break
        yield temp
        count += 1


def get_translation(n):
    return dt.Vector(pm.xform(n, worldSpace=1, translation=1, query=1))


def get_rotation(n):
    return pm.xform(n, worldSpace=1, rotation=1, query=1)