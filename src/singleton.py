import inspect


class Singleton(type):
    def __call__(cls, *args, **kwargs):
        signature = inspect.signature(super().__call__)
        ctor = signature.bind(*args, **kwargs)
        ctor.apply_defaults()
        key = str(ctor)
        if key not in cls.objs:
            cls.objs[key] = super().__call__(*args, **kwargs)

        return cls.objs[key]

