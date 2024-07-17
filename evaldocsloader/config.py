from os import environ

from mkdocs.config import Config, config_options as opt

class EvalDocsLoaderConfig(Config):
    # Function metadata options
    functions_announce_endpoint = opt.Type(str)
    api_key = opt.Type(str)
    max_workers = opt.Type(int, default=0)

    # GitHub options
    github_owner = opt.Type(str, default="lambda-feedback")
    github_topic = opt.Type(str, default="evaluation-function")
    github_token = opt.Type(str, default=environ.get("GITHUB_TOKEN"))

    # Section names
    dev_section = opt.ListOfItems(opt.Type(str))
    user_section = opt.ListOfItems(opt.Type(str))
