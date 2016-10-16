from collections import OrderedDict, namedtuple

from six import python_2_unicode_compatible


MessagePart = namedtuple('MessagePart', ['element', 'type'])


class AbstractMessage(object):
    """Messages consist of one or more logical parts.

    Each part is associated with a type from some type system using a
    message-typing attribute. The set of message-typing attributes is
    extensible. WSDL defines several such message-typing attributes for use
    with XSD:

        element: Refers to an XSD element using a QName.
        type: Refers to an XSD simpleType or complexType using a QName.

    """
    def __init__(self, name):
        self.name = name
        self.parts = OrderedDict()

    def __repr__(self):
        return '<%s(name=%r)>' % (self.__class__.__name__, self.name.text)

    def resolve(self, definitions):
        pass

    def add_part(self, name, element):
        self.parts[name] = element


class AbstractOperation(object):
    """Abstract operations are defined in the wsdl's portType elements."""

    def __init__(self, name, input_message=None, output_message=None,
                 fault_messages=None, parameter_order=None):
        """Initialize the abstract operation.

        :param name: The name of the operation
        :type name: str
        :param input_message: Message to generate the request XML
        :type input_message: AbstractMessage
        :param output_message: Message to process the response XML
        :type output_message: AbstractMessage
        :param fault_messages: Dict of messages to handle faults
        :type fault_messages: dict of str: AbstractMessage

        """
        self.name = name
        self.input_message = input_message
        self.output_message = output_message
        self.fault_messages = fault_messages
        self.parameter_order = parameter_order


class PortType(object):
    def __init__(self, name, operations):
        self.name = name
        self.operations = operations

    def __repr__(self):
        return '<%s(name=%r)>' % (
            self.__class__.__name__, self.name.text)

    def resolve(self, definitions):
        pass


@python_2_unicode_compatible
class Binding(object):
    """Base class for the various bindings (SoapBinding / HttpBinding)

        Binding
           |
           +-> Operation
                   |
                   +-> ConcreteMessage
                             |
                             +-> AbstractMessage

    """
    def __init__(self, wsdl, name, port_name):
        """Binding

        :param wsdl:
        :type wsdl:
        :param name:
        :type name: string
        :param port_name:
        :type port_name: string

        """
        self.name = name
        self.port_name = port_name
        self.port_type = None
        self.wsdl = wsdl
        self._operations = {}

    def resolve(self, definitions):
        self.port_type = definitions.get('port_types', self.port_name.text)
        for operation in self._operations.values():
            operation.resolve(definitions)

    def _operation_add(self, operation):
        # XXX: operation name is not unique
        self._operations[operation.name] = operation

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self.name.text)

    def __repr__(self):
        return '<%s(name=%r, port_type=%r)>' % (
            self.__class__.__name__, self.name.text, self.port_type)

    def get(self, name):
        return self._operations.get(name)

    @classmethod
    def match(cls, node):
        raise NotImplementedError()

    @classmethod
    def parse(cls, definitions, xmlelement):
        raise NotImplementedError()


@python_2_unicode_compatible
class Operation(object):
    """Concrete operation

    Contains references to the concrete messages

    """
    def __init__(self, name, binding):
        self.name = name
        self.binding = binding
        self.abstract = None
        self.style = None
        self.input = None
        self.output = None
        self.faults = {}

    def resolve(self, definitions):
        self.abstract = self.binding.port_type.operations[self.name]

    def __repr__(self):
        return '<%s(name=%r, style=%r)>' % (
            self.__class__.__name__, self.name, self.style)

    def __str__(self):
        if not self.input:
            return u'%s(missing input message)' % (self.name)

        retval = u'%s(%s)' % (self.name, self.input.signature())
        if self.output:
            retval += u' -> %s' % (self.output.signature(as_output=True))
        return retval

    def create(self, *args, **kwargs):
        return self.input.serialize(*args, **kwargs)

    def process_reply(self, envelope):
        raise NotImplementedError()

    @classmethod
    def parse(cls, wsdl, xmlelement, binding):
        """
            <wsdl:operation name="nmtoken"> *
               <-- extensibility element (2) --> *
               <wsdl:input name="nmtoken"? > ?
                   <-- extensibility element (3) -->
               </wsdl:input>
               <wsdl:output name="nmtoken"? > ?
                   <-- extensibility element (4) --> *
               </wsdl:output>
               <wsdl:fault name="nmtoken"> *
                   <-- extensibility element (5) --> *
               </wsdl:fault>
            </wsdl:operation>
        """
        raise NotImplementedError()


@python_2_unicode_compatible
class Port(object):
    def __init__(self, name, binding_name, xmlelement):
        self.name = name
        self._resolve_context = {
            'binding_name': binding_name,
            'xmlelement': xmlelement,
        }

        # Set during resolve()
        self.binding = None
        self.binding_options = None

    def __repr__(self):
        return '<%s(name=%r, binding=%r, %r)>' % (
            self.__class__.__name__, self.name, self.binding,
            self.binding_options)

    def __str__(self):
        return u'Port: %s (%s)' % (self.name, self.binding)

    def resolve(self, definitions):
        if self._resolve_context is None:
            return

        try:
            binding = definitions.get(
                'bindings', self._resolve_context['binding_name'].text)
        except IndexError:
            return False

        self.binding = binding
        self.binding_options = binding.process_service_port(
            self._resolve_context['xmlelement'])
        self._resolve_context = None
        return True


@python_2_unicode_compatible
class Service(object):

    def __init__(self, name):
        self.ports = OrderedDict()
        self.name = name
        self._is_resolved = False

    def __str__(self):
        return u'Service: %s' % self.name

    def __repr__(self):
        return '<%s(name=%r, ports=%r)>' % (
            self.__class__.__name__, self.name, self.ports)

    def resolve(self, definitions):
        if self._is_resolved:
            return

        unresolved = []
        for name, port in self.ports.items():
            is_resolved = port.resolve(definitions)
            if not is_resolved:
                unresolved.append(name)

        # Remove unresolved bindings (http etc)
        for name in unresolved:
            del self.ports[name]

        self._is_resolved = True

    def add_port(self, port):
        self.ports[port.name] = port
