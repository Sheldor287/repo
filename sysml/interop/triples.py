
triples = [
    # Manufacturing
    ("Ford", "manufactures", "Mustang"),
    ("Ford", "manufactures", "F-150"),
    ("Toyota", "manufactures", "Camry"),
    ("Toyota", "manufactures", "Corolla"),
    ("Chevrolet", "manufactures", "Silverado"),
    ("Honda", "manufactures", "Civic"),

    # Engines
    ("Mustang", "hasEngine", "Coyote V8"),
    ("F-150", "hasEngine", "EcoBoost V6"),
    ("Camry", "hasEngine", "Dynamic Force I4"),
    ("Corolla", "hasEngine", "Dynamic Force I4"),
    ("Silverado", "hasEngine", "EcoTec3 V8"),
    ("Civic", "hasEngine", "Honda I4"),

    # Platforms
    ("Mustang", "usesPlatform", "Ford CD6"),
    ("F-150", "usesPlatform", "Ford T3"),
    ("Camry", "usesPlatform", "Toyota TNGA-K"),
    ("Corolla", "usesPlatform", "Toyota TNGA-C"),
    ("Silverado", "usesPlatform", "GM T1XX"),
    ("Civic", "usesPlatform", "Honda Compact Platform"),

    # Assembly plants
    ("Mustang", "assembledAt", "Flat Rock Plant"),
    ("F-150", "assembledAt", "Dearborn Truck Plant"),
    ("Camry", "assembledAt", "Georgetown Plant"),
    ("Corolla", "assembledAt", "Mississippi Plant"),
    ("Silverado", "assembledAt", "Fort Wayne Plant"),
    ("Civic", "assembledAt", "Indiana Auto Plant"),

    # Fuel types
    ("Mustang", "hasFuelType", "Gasoline"),
    ("F-150", "hasFuelType", "Gasoline"),
    ("Camry", "hasFuelType", "Hybrid"),
    ("Corolla", "hasFuelType", "Gasoline"),
    ("Silverado", "hasFuelType", "Gasoline"),
    ("Civic", "hasFuelType", "Gasoline"),

    # Corporate relationships
    ("Ford", "headquarteredIn", "Dearborn"),
    ("Toyota", "headquarteredIn", "Toyota City"),
    ("Chevrolet", "ownedBy", "General Motors"),
    ("Honda", "headquarteredIn", "Tokyo"),
]

object_definitions = {
    # Automotive Brands & Manufacturers
    "Chevrolet": "Automotive brand under General Motors",
    "Ford": "American multinational automotive manufacturer",
    "General Motors": "American multinational automotive manufacturing corporation",
    "Honda": "Japanese multinational automotive manufacturer",
    "Toyota": "Japanese multinational automotive manufacturer",

    # Vehicle Models
    "Camry": "Mid-size sedan produced by Toyota",
    "Civic": "Compact car produced by Honda",
    "Corolla": "Compact car produced by Toyota",
    "F-150": "Full-size pickup truck produced by Ford",
    "Mustang": "Pony/sports car produced by Ford",
    "Silverado": "Full-size pickup truck produced by Chevrolet",

    # Engines & Powertrains
    "Coyote V8": "5.0L naturally aspirated V8 engine by Ford",
    "Dynamic Force I4": "Family of inline-four gasoline and hybrid engines by Toyota",
    "EcoBoost V6": "Twin-turbocharged direct-injection V6 engine family by Ford",
    "EcoTec3 V8": "Small block V8 engine family by General Motors",
    "Honda I4": "Inline-four cylinder engine produced by Honda",

    # Vehicle Platforms
    "Ford CD6": "Rear-wheel drive/all-wheel drive platform by Ford",
    "Ford T3": "Full-size body-on-frame truck platform by Ford",
    "GM T1XX": "Full-size body-on-frame truck platform by General Motors",
    "Honda Compact Platform": "Global architecture for compact vehicles by Honda",
    "Toyota TNGA-C": "Modular compact vehicle platform by Toyota",
    "Toyota TNGA-K": "Modular mid-size to full-size vehicle platform by Toyota",

    # Assembly Plants
    "Dearborn Truck Plant": "Ford assembly plant located in Dearborn, Michigan",
    "Flat Rock Plant": "Ford assembly plant located in Flat Rock, Michigan",
    "Fort Wayne Plant": "General Motors assembly plant located in Roanoke, Indiana",
    "Georgetown Plant": "Toyota Motor Manufacturing Kentucky plant in Georgetown, Kentucky",
    "Indiana Auto Plant": "Honda manufacturing facility located in Greensburg, Indiana",
    "Mississippi Plant": "Toyota Motor Manufacturing Mississippi plant in Blue Springs, Mississippi",

    # Locations
    "Dearborn": "City in Michigan, home to Ford Motor Company headquarters",
    "Tokyo": "Capital of Japan and headquarters location for Honda",
    "Toyota City": "City in Aichi Prefecture, Japan, home to Toyota Motor Corporation headquarters",

    # Fuel / Powertrain Types
    "Gasoline": "Internal combustion fuel type using refined petroleum",
    "Hybrid": "Powertrain combining an internal combustion engine with one or more electric motors",
}

predicate_definitions = {
    "assembledAt": "Vehicle model is assembled at a manufacturing plant facility",
    "hasEngine": "Vehicle model is equipped with a specific engine or powertrain",
    "hasFuelType": "Vehicle model utilizes a primary fuel or propulsion type",
    "headquarteredIn": "Organization or corporation is headquartered in a specific geographic location",
    "manufactures": "Automotive manufacturer produces a specific vehicle model",
    "ownedBy": "Brand or subsidiary organization is owned by a parent corporation",
    "usesPlatform": "Vehicle model is constructed on a specific automotive architecture or platform",
}


predicate_definitions_mapping = {
    "assembledAt": {
        "definition": "Vehicle model is assembled at a manufacturing plant facility",
        "uml_equivalent": "uml:Association (Directed Dependency or General Association)",
        "sysml_equivalent": "sysml:Allocate (or Directed Allocation Relationship)"
    },
    "hasEngine": {
        "definition": "Vehicle model is equipped with a specific engine or powertrain",
        "uml_equivalent": "uml:Property (Composition / Composite Aggregation)",
        "sysml_equivalent": "sysml:PartProperty (Block Definition Diagram composition)"
    },
    "hasFuelType": {
        "definition": "Vehicle model utilizes a primary fuel or propulsion type",
        "uml_equivalent": "uml:Property (Value Attribute / Enumeration Reference)",
        "sysml_equivalent": "sysml:ValueProperty (Typed by a ValueType)"
    },
    "headquarteredIn": {
        "definition": "Organization or corporation is headquartered in a specific geographic location",
        "uml_equivalent": "uml:Association (Directed Association / Dependency)",
        "sysml_equivalent": "sysml:DirectedRelationship (or Item Flow / Dependency)"
    },
    "manufactures": {
        "definition": "Automotive manufacturer produces a specific vehicle model",
        "uml_equivalent": "uml:Association (Navigable Directed Association)",
        "sysml_equivalent": "sysml:DirectedRelationship (or Action / Item Flow)"
    },
    "ownedBy": {
        "definition": "Brand or subsidiary organization is owned by a parent corporation",
        "uml_equivalent": "uml:Aggregation (Shared Aggregation) / Package Ownership",
        "sysml_equivalent": "sysml:SharedProperty (or Ownership Dependency)"
    },
    "usesPlatform": {
        "definition": "Vehicle model is constructed on a specific automotive architecture or platform",
        "uml_equivalent": "uml:Generalization (or Directed Dependency)",
        "sysml_equivalent": "sysml:Specialization (or <<ref>> Reference Property / Realization)"
    }
}