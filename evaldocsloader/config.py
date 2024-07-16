from os import environ

from mkdocs.config import Config, config_options as opt

class EvalDocsLoaderConfig(Config):
    # Function metadata options
    function_announce_endpoint = opt.Type(str, required=True)
    api_key = opt.Type(str, required=True)

    # GitHub options
    github_owner = opt.Type(str, required=True, default="lambda_feedback")
    github_topic = opt.Type(str, required=True, default="evaluation_function")
    github_token = opt.Type(str, required=True, default=environ.get("GITHUB_TOKEN"))

    # Section names
    dev_section = opt.ListOfItems(opt.Type(str), required=True)
    user_section = opt.ListOfItems(opt.Type(str), required=True)
