from os import environ

from mkdocs.config import Config, config_options as opt

class FunctionLoaderConfig(Config):
    announce_endpoint = opt.Type(str, required=False)
    api_key = opt.Type(str, required=False)

class RepoLoaderConfig(Config):
    owner = opt.Type(str, required=False, default="lambda_feedback")
    tags = opt.ListOfItems(opt.Type(str), required=False, default=["evaluation_function"])
    token = opt.Type(str, required=False, default=environ.get("GITHUB_TOKEN"))

class EvalDocsLoaderConfig(Config):
    # Sources
    source = opt.Choice(['function', 'repository'], required=True, default='function')
    function = opt.SubConfig(FunctionLoaderConfig)
    repository = opt.SubConfig(RepoLoaderConfig)

    # Section names
    dev_section = opt.ListOfItems(opt.Type(str), required=True)
    user_section = opt.ListOfItems(opt.Type(str), required=True)

    # Deprecated options (moved to function)
    functions_announce_endpoint = opt.Deprecated(
        moved_to='function.announce_endpoint',
        message='Use function.announce_endpoint instead',
        option_type=opt.Type(str, required=False),
    )
    api_key = opt.Deprecated(
        moved_to='function.api_key',
        message='Use function.api_key instead',
        option_type=opt.Type(str, required=False),
    )