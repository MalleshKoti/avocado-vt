"""
Class which allows property and dict-like access to a fixed set of instance
attributes.  Attributes are locked by __slots__, however accessor methods
may be created/removed on instances, or defined by the subclass.  An
INITIALIZED attribute is provided to signel completion of __init__()
for use by accessor methods (i.e. so they know when __init__ may be
setting values).

Subclasses must define a __slots__ class attribute containing the list
of attribute names to reserve.  All additional subclass descendents
must explicitly copy __slots__ from the parent in their definition.

Users of subclass instances are expected to get/set/del attributes
only via the standard object or dict-like interface.  i.e.

instance.attribute = whatever
or
instance['attribute'] = whatever

Internally, methods are free to call the accessor methods.  Only
accessor methods should use the special dict_*() and super_*() methods.
These are there to allow convenient access to the internal dictionary
values and subclass-defined attributes (such as __slots__).

example:

class A(PropCan):
   # Class with *attributes*
    __slots__ = ('a', 'b')
    # 'a' has defined a set/get/del by definition of method with prefix
    #     set_a, get_a, del_a
    # 'b' doesn't have defined set/get/del then classic set/get/del will be
    #     called instead.


    def __init__(self, a=1, b='b'):
       super(A, self).__init__(a, b)


    def set_a(self, value)
        # If is_instance(obj, A) then obj.a = "val" call this method.
        dict_set("a", value)


    def get_a(self, value)
        # If is_instance(obj, A) then xx = obj.a call this method.
        return dict_get("a")


    def del_a(self, value)
        # If is_instance(obj, A) then del obj.a call this method.
        dict_del("a")


class B(PropCan):
   # Class without *attributes*
   # ***** Even if class doesn't have attributes there should be
   # defined __slots__ = []. Because it is preferred by new style of class.
   # *****
    __slots__ = []


    def __init__(self):
       super(B, self).__init__()
"""


class PropCanInternal(object):

    """
    Semi-private methods for use only by PropCanBase subclasses (NOT instances)
    """

    # The following methods are intended for use by accessor-methods
    # where they may need to bypass the special attribute/key handling

    def dict_get(self, key):
        """
        Get a key unconditionally, w/o checking for accessor method or __slots__
        """
        return dict.__getitem__(self, key)

    def dict_set(self, key, value):
        """
        Set a key unconditionally, w/o checking for accessor method or __slots__
        """
        dict.__setitem__(self, key, value)

    def dict_del(self, key):
        """
        Del key unconditionally, w/o checking for accessor method or __slots__
        """
        return dict.__delitem__(self, key)

    def super_get(self, key):
        """
        Get attribute unconditionally, w/o checking accessor method or __slots__
        """
        return object.__getattribute__(self, key)

    def super_set(self, key, value):
        """
        Set attribute unconditionally, w/o checking accessor method or __slots__
        """
        object.__setattr__(self, key, value)

    def super_del(self, key):
        """
        Del attribute unconditionally, w/o checking accessor method or __slots__
        """
        object.__delattr__(self, key)


class PropCanBase(dict, PropCanInternal):

    """
    Objects with optional accessor methods and dict-like access to fixed set of keys
    """
    INITIALIZED = False

    def __new__(cls, *args, **dargs):
        if not hasattr(cls, '__slots__'):
            raise NotImplementedError("Class '%s' must define __slots__ "
                                      "property" % str(cls))
        newone = super(PropCanBase, cls).__new__(cls, *args, **dargs)
        return newone

    def __init__(self, *args, **dargs):
        """
        Initialize contents directly or by way of accessors

        :param *args: Initial values for __slots__ keys, same as dict.
        :param **dargs: Initial values for __slots__ keys, same as dict.
        """
        # Params are initialized here, not in super
        super(PropCanBase, self).__init__()
        # No need to re-invent dict argument processing
        values = dict(*args, **dargs)
        for key in self.super_get("__all_slots"):
            value = values.get(key, "@!@!@!SENTINEL!@!@!@")
            if value is not "@!@!@!SENTINEL!@!@!@":
                # Call accessor methods if present
                self[key] = value
        # Let accessor methods know initialization is complete
        self.super_set('INITIALIZED', True)


    @classmethod
    def get_all_slots(cls):
        slots = []
        for cls_slots in [getattr(_cls, '__slots__', [])
                                               for _cls in cls.__mro__]:
            slots += cls_slots
        return slots


    def __getitem__(self, key):
        try:
            accessor = super(PropCanBase,
                             self).__getattribute__('get_%s' % key)
        except AttributeError:
            return super(PropCanBase, self).__getitem__(key)
        return accessor()

    def __setitem__(self, key, value):
        self.__canhaz__(key, KeyError)
        try:
            accessor = super(PropCanBase,
                             self).__getattribute__('set_%s' % key)
        except AttributeError:
            return super(PropCanBase, self).__setitem__(key, value)
        return accessor(value)

    def __delitem__(self, key):
        try:
            accessor = super(PropCanBase,
                             self).__getattribute__('del_%s' % key)
        except AttributeError:
            return super(PropCanBase, self).__delitem__(key)
        return accessor()

    def __getattr__(self, key):
        try:
            # Attempt to call accessor methods first whenever possible
            self.__canhaz__(key, KeyError)
            return self.__getitem__(key)
        except KeyError:
            # Allow subclasses to define attributes if required
            return super(PropCanBase, self).__getattribute__(key)

    def __setattr__(self, key, value):
        self.__canhaz__(key)
        try:
            return self.__setitem__(key, value)
        except KeyError, detail:
            # Prevent subclass instances from defining normal attributes
            raise AttributeError(str(detail))

    def __delattr__(self, key):
        self.__canhaz__(key)
        try:
            return self.__delitem__(key)
        except KeyError, detail:
            # Prevent subclass instances from deleting normal attributes
            raise AttributeError(str(detail))

    def __canhaz__(self, key, excpt=AttributeError):
        """
        Quickly determine if an accessor or instance attribute name is defined.
        """
        slots = tuple(self.super_get("__all_slots"))
        keys = slots + ('get_%s' % key, 'set_%s' % key, 'del_%s' % key)
        if key not in keys:
            raise excpt("Key '%s' not found in super class attributes or in %s"
                        % (str(key), str(keys)))

    def copy(self):
        """
        Copy properties by value, not by reference.
        """
        return self.__class__(dict(self))


class PropCan(PropCanBase):

    """
    Special value handling on retrieval of None values
    """

    def __len__(self):
        length = 0
        for key in self.super_get("__all_slots"):
            # special None/False value handling
            if self.__contains__(key):
                length += 1
        return length

    def __contains__(self, key):
        try:
            value = self.dict_get(key)
        except (KeyError, AttributeError):
            return False
        # Avoid inf. recursion if value == self
        if issubclass(type(value), type(self)) or value:
            return True
        return False

    def __eq__(self, other):
        # special None/False value handling
        return dict([(key, value) for key, value in self.items()]) == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def keys(self):
        # special None/False value handling
        return [key for key in self.super_get("__all_slots")
                                                    if self.__contains__(key)]


    def values(self):
        # special None/False value handling
        return [self[key] for key in self.keys()]

    def items(self):
        return tuple([(key, self[key]) for key in self.keys()])

    has_key = __contains__

    def set_if_none(self, key, value):
        """
        Set the value of key, only if it's not set or None
        """
        if not key in self:
            self[key] = value

    def set_if_value_not_none(self, key, value):
        """
        Set the value of key, only if value is not None
        """
        if value:
            self[key] = value

    def __str__(self):
        """
        Guarantee return of string format dictionary representation
        """
        acceptable_types = (str, unicode, int, float, long)
        return str(dict([(key, value) for key, value in self.items()
                         if issubclass(type(value), acceptable_types)]))

    __repr__ = __str__
