from invoke import Collection
from . import clean, deps, docs, pypi, new_ac


namespace = Collection(clean, deps, docs, pypi, new_ac)
