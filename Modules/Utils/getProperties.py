def get_properties_from_yaml(property):
    import yaml

    with open("parameters.yml", "r") as file:
        properties = yaml.safe_load(file)
        print(f"Propiedades cargadas: {properties}")
        return properties.get(property)