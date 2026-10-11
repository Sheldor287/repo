from abc import ABC, abstractmethod

class BarcodeValidator(ABC):
    """
    Each barcode type has a specific length and checksum algorithm. 
    This abstract base class defines the interface for barcode validators, checking for length and checksum rules.
    Subclasses must implement the check_sum method to provide the specific checksum validation logic for each barcode type.
    """
    name = ""
    valid_lengths = ()

    def matches_length(self, code):
        return len(code) in self.valid_lengths
    
    @abstractmethod
    def check_sum(self, code):
        pass

    def validate(self, code):
        if not self.matches_length(code):
            return False
        return self.check_sum(code)
    
class UPCValidator(BarcodeValidator):
    name = "UPC-A"
    valid_lengths = (12,)

    def check_sum(self, code):
        odd_sum = sum(int(code[i]) for i in range(0, len(code), 2))
        even_sum = sum(int(code[i]) for i in range(1, len(code), 2))
        total_sum = odd_sum * 3 + even_sum
        return total_sum % 10 == 0
    
class EAN13Validator(BarcodeValidator):
    name = "EAN-13"
    valid_lengths = (13,)

    def check_sum(self, code):
        if code.startswith("978") or code.startswith("979"):
            return False
        else:
            odd_sum = sum(int(code[i]) for i in range(0, len(code), 2))
            even_sum = sum(int(code[i]) for i in range(1, len(code), 2))
            total_sum = odd_sum + even_sum * 3
            return total_sum % 10 == 0
    
class EAN8Validator(BarcodeValidator):
    name = "EAN-8"
    valid_lengths = (8,)

    def check_sum(self, code):
        odd_sum = sum(int(code[i]) for i in range(0, len(code), 2))
        even_sum = sum(int(code[i]) for i in range(1, len(code), 2))
        total_sum = odd_sum * 3 + even_sum
        return total_sum % 10 == 0
    
class GTIN14Validator(BarcodeValidator):
    name = "GTIN"
    valid_lengths = (14,)

    def check_sum(self, code):
        odd_sum = sum(int(code[i]) for i in range(0, len(code), 2))
        even_sum = sum(int(code[i]) for i in range(1, len(code), 2))
        total_sum = odd_sum * 3 + even_sum
        return total_sum % 10 == 0
    
class ISBN10Validator(BarcodeValidator):
    name = "ISBN-10"
    valid_lengths = (10,)

    def check_sum(self, code):
        total = sum((10 - i) * int(code[i]) for i in range(9))
        total += int(code[-1])
        return total % 11 == 0
    
class ISBN13Validator(BarcodeValidator):
    name = "ISBN-13"
    valid_lengths = (13,)

    def check_sum(self, code):
            if code.startswith("978") or code.startswith("979"):
                odd_sum = sum(int(code[i]) for i in range(0, len(code), 2))
                even_sum = sum(int(code[i]) for i in range(1, len(code), 2))
                total_sum = odd_sum + even_sum * 3
                return total_sum % 10 == 0
            else:
                return False
    
class ISSNValidator(BarcodeValidator):
    name = "ISSN"
    valid_lengths = (8,)

    def check_sum(self, code):
        total_sum = sum((8 - i) * int(code[i]) for i in range(len(code) - 1))
        check_digit = int(code[-1])
        return (total_sum + check_digit) % 11 == 0
    
validators = [
    UPCValidator(),
    EAN13Validator(),
    EAN8Validator(),
    GTIN14Validator(),
    ISBN10Validator(),
    ISBN13Validator(),
    ISSNValidator()
]

class BarcodeDetector:

    def __init__(self, validators):
        self.validators = validators

    def detect(self, code):
        code = code.replace("-", "").replace(" ", "")
        for validator in self.validators:
            if validator.matches_length(code) and validator.validate(code):
                return validator.name