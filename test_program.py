import time


def p():
    x = 0.5
    b = 20
    f()
    g(b)
    y = 4


def f():
    m()


def g(b):
    k = b + 10


def m():
    time.sleep(2)
    c = 9

if __name__=="__main__":
    p()