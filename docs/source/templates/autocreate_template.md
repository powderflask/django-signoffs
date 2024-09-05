# {{ module.name }}

```{autodoc2-summary}
:renderer: myst

{% for object in module.object_paths.values() %}
{{ object }}{% endfor %}
```

{% for object in module.object_paths.values() %}
```{autodoc2-object} {{ object }}
render_plugin = "myst"
```{% endfor %}