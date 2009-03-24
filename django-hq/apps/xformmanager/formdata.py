from lxml import etree
import logging
import re

#This class is probably unnecessary and more hassle than it's worth
class ElementData(object):
    """ This class holds xml instance data.
    
    It is basically a wrapper for lxml.etree. 
    
    """    
    
    def __init__(self, stream_pointer):
        logging.debug("ElementData: create form data object")
        #put in checking to make sure this returns properly even when inputting bad data
        self.tree = etree.parse(stream_pointer)
        self.element = self.tree.getroot()

    def find(self, xpath):
        return self.element.find(xpath)
    
    def find_all(self, xpath):
        return self.element.find_all(xpath)
    
    def xpath(self, location, namespaces):
        return (self.tree).xpath(location, namespaces=namespaces)
    
    def next(self):
        self.element = self.iter.next()
        return self.element
    
    def getroot(self):
        return self.element
    
    def get_xmlns(self):
        r = re.search('{[a-zA-Z0-9\.\/\:]*}', self.element.tag)
        xmlns = r.group(0).strip('{').strip('}')
        return xmlns
    
    def __str__(self):
        return etree.tostring(self.tree)
    
    # abstract to generic separator
    def toCSV(self):
        if len(self.element) == 0:
            csv = self.element.tag + '\n' + self.element.text
            return csv
        field_values = self.__get_csv( self.element, '' )
        csv = self.__trim2chars(field_values['fields']) + '\n' + self.__trim2chars(field_values['values'])
        return csv

    def __get_csv( self, parent, parent_info ):
        fields = ''
        values = ''
        siblings = []
        for child in parent:
            name = child.tag
            i = 2
            while name in siblings:
                name = child.tag + str(i)
                i = i + 1
            current_info = self.__join( parent_info, self.__remove_namespace(name))
            field_values = self.__get_csv(  child , current_info )
            if len(child) == 0:
                fields = fields + current_info + ', ' + field_values['fields']
                values  = values + child.text.strip() + ', ' + field_values['values']
            else:
                fields = fields + field_values['fields']
                values  = values + field_values['values']                
            siblings.append(name)
        return {'fields':fields, 'values':values}
    
    #hack - remove this later
    def __trim2chars(self, string):
        return string[0:len(string)-2]
    
    def __remove_namespace(self, text):
        start = text.rfind('}') + 1
        end = len(text)
        return text[ start:end ]
    
    def __join(self, first_part, second_part):
        if first_part is '':
            return second_part
        return first_part + "_" + second_part
    
class FormData(ElementData):
    """ This class holds xml instance data (presumably representing an xsd form schema) """
    pass
