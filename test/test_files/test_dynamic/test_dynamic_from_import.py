from test_dynamic_func import func_1

def func_3(func):
    return func()


a=func_3(func_1)
print(a)
