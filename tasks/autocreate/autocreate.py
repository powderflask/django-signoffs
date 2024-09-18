import os
import jinja2
import importlib.util
import dataclasses as dc
from typing import List, Optional
from dataclasses import dataclass, fields
from tasks.autocreate.module import Module
from tasks.autocreate.resolver import Resolver
from tasks.autocreate.utils import DisplayText, get_fields, render_to_file


# Default configuration options
CFG_DEFAULTS = {
    "cfg_file": "docs/source/conf.py",
    "db_file": "autodoc.db.json",
    "output_dir": "docs/source/autocreate_docs",
    "template_dir": "docs/templates",
    "doc_template": "autocreate_template.md",
    "index_template": "autocreate_index_template.md",
    "file_ext": ".md",
    "exclude_regexes": None,
    "target_var": "__all__",
}
PKG_DEFAULTS = {}  # TODO: something with this


@dataclass
class Cfg:
    package_root: str
    package_name: Optional[str] = None
    target_var: str = CFG_DEFAULTS['target_var']
    db_file: str = CFG_DEFAULTS['db_file']
    doc_template: str = CFG_DEFAULTS["doc_template"]
    file_ext: str = CFG_DEFAULTS["file_ext"]
    index_template: str = CFG_DEFAULTS["index_template"]
    template_dir: str = CFG_DEFAULTS["template_dir"]
    output_dir: str = CFG_DEFAULTS["output_dir"]
    exclude_regexes: Optional[List[str]] = CFG_DEFAULTS['exclude_regexes']

    @classmethod
    def required_options(cls) -> List[str]:
        """
        Property that returns a list of all required options for initializing the Cfg object.
        """
        return [f.name for f in fields(cls) if f.default == dc.MISSING and f.default_factory == dc.MISSING]

    @classmethod
    def load_conf_opts(cls, config_path: str) -> dict:
        """
        :return: the dict of cfg options
        """
        opt_names = get_fields(cls)

        spec = importlib.util.spec_from_file_location('conf', config_path)
        conf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conf)
        pkg_opts = getattr(conf, 'autocreate_pkg_options', {})
        gen_opts = getattr(conf, 'autocreate_options', {})

        chosen = {}
        opt_hierarchy = [pkg_opts, gen_opts, PKG_DEFAULTS, CFG_DEFAULTS]  # The order of from_dict sources that the cfg options are pulled from
        for opt_set in opt_hierarchy:
            chosen.update(**{opt_names.pop(opt_names.index(k)): v for k, v in opt_set.items() if k in opt_names})
        # Any remaining names in opt_names can be assumed to correspond to an empty field
        return chosen

    @classmethod
    def from_config_file(cls, config_path: str) -> 'Cfg':
        """
        Class method to initialize a new Cfg instance from the autocreate_options
        dictionary in the specified config file.
        """

        cfg_options = cls.load_conf_opts(config_path)
        if_missing = lambda f: f.name not in cfg_options.keys()  # TODO: Write a test for this instead
        missing_options = get_fields(cls, if_missing)
        if missing_options:
            raise ValueError(f"Missing required configuration options:\n"+'\n'.join(['\t'+opt for opt in missing_options]))
        return cls(**cfg_options)


def auto_create(cfg_path: str = CFG_DEFAULTS['cfg_file'], silent: bool = False):
    dt = DisplayText(silent=silent)
    arrow = '-->'
    cfg = Cfg.from_config_file(cfg_path)
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(cfg.template_dir))
    dt.verbose(f"\n{dt.wrap(arrow, 'H')} Finding Modules...")
    modules = Module.init_all_from_dir(from_dir=cfg.package_root, exclude_regexes=cfg.exclude_regexes)
    if not modules:
        dt.verbose(f"{dt.wrap('Generation Failed. No modules found in', 'F')} {dt.wrap(cfg.package_root, 'GRN')}")
        return
    if not os.path.exists(cfg.output_dir):
        os.mkdir(cfg.output_dir)
        dt.verbose(f"{dt.wrap(arrow, 'WRN')} Created Output Directory: {dt.wrap(cfg.output_dir, 'GRN')}")

    dt.verbose(f"{dt.wrap(arrow, 'H')} {dt.wrap(len(modules), 'CYN')} Modules Found to Document...", '\n')
    documented_modules = []
    for module in modules:
        resolver = Resolver(module.file_path, cfg.db_file)
        resolver.resolve_module()
        if resolver.invalid_paths:
            dt.verbose(
                f"\n{dt.wrap(arrow, 'F')} Unable to resolve {dt.wrap(str(len(resolver.invalid_paths)), 'F')} paths in {dt.wrap(module.file_path, 'WRN')}:\n",
                *[f"\t{dt.wrap(name, 'WRN')}\n\t└─> {dt.wrap(path, 'F')}\n" for name, path in resolver.invalid_paths.items()],
            )
        if not resolver.obj_paths:
            dt.verbose(f"{dt.wrap(arrow, 'F')} No Matching Objects found in {dt.wrap(module.file_path, 'F')}")
            continue
        output_dir = f"{cfg.output_dir}/{cfg.package_name}"
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
            dt.verbose(f"{dt.wrap('└─>', 'WRN')} Created Directory: {dt.wrap(cfg.output_dir, 'GRN')}")

        module.object_paths = resolver.obj_paths
        module.doc_file_path = f"{output_dir}/{module.get_display_name}{cfg.file_ext}"
        context = dict(module=module)
        render_to_file(file_path=module.doc_file_path, template=cfg.doc_template, env=template_env, **context)
        documented_modules.append(module)
        dt.verbose(f"{dt.wrap(arrow, 'GRN')} Created Doc for {dt.wrap(module.file_path, 'GRN')}")

    if documented_modules:
        index_context = dict(modules=documented_modules, package_name=cfg.package_name)
        index_file_path = f"{cfg.output_dir}/{cfg.package_name}_index{cfg.file_ext}"
        render_to_file(file_path=index_file_path, template=cfg.index_template, env=template_env, **index_context)
        dt.verbose(f"\n{dt.wrap(arrow, 'GRN')} Created index file: {dt.wrap(index_file_path, 'GRN')}")
    dt.verbose(dt.wrap("Finished", 'GRN', 'B'))
