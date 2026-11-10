"""Compile bounded shared rigid frames, independently of surface coordinates."""
import re
from .expressions import compile_expression, ALLOWED
from .scenes import SceneError, _number, _LAYER_ID

# An assembly is one rigid frame for whole surfaces: no surface coordinate or binding is in scope.
ASSEMBLY_ALLOWED=ALLOWED.replace('the names u v t pi','the names t and pi only (no u, v or bindings)')


def compile_assemblies(groups):
    from .worlds import fields, shown
    if not isinstance(groups,list) or len(groups)>8:
        raise SceneError('World allows at most eight assemblies: scene.assemblies is an array of 0-8 objects; got '
                         +(f'{len(groups)} items' if isinstance(groups,list) else shown(groups)))
    result={}
    for group in groups:
        fields(group,'id translation rotation pivot scale','assembly','parent')
        identifier=group['id']
        if not isinstance(identifier,str) or not _LAYER_ID.fullmatch(identifier) or identifier in result:
            raise SceneError('Assembly IDs must be unique valid 1-40 character identifiers using only letters, digits, underscore or hyphen; '
                             f'got {shown(identifier)}'+(', which an earlier assembly already uses' if isinstance(identifier,str) and identifier in result else ''))
        parent=group.get('parent')
        if 'parent' in group and (not isinstance(parent,str) or parent not in result):
            raise SceneError(f'Assembly parent must precede its child; no cycles or forward references: got {shown(parent)}; '
                             'assemblies defined before this one: '+(', '.join(sorted(result)) if result else 'none, so omit parent or list the parent first'))
        depth=1+(result[parent]['depth'] if parent is not None else 0)
        if depth>4:raise SceneError(f'Assembly hierarchy exceeds four levels at {shown(identifier)}: attach it to a shallower parent')
        for field,low,high in [('pivot',-80,80),('scale',.05,8)]:
            values=group[field]
            if not isinstance(values,list) or len(values)!=3:
                raise SceneError(f'Assembly {field} needs three values: pass an array of three numbers between {low} and {high}; got {shown(values)}')
            for value in values:_number(value,low,high,'assembly '+field)
        compiled={};cost=60  # fixed vector, scale and Euler rotation work per level
        for field in ('translation','rotation'):
            exprs=group[field]
            fields(exprs,'x y z','assembly '+field)
            compiled[field]=[]
            for axis in ('x','y','z'):
                text=exprs[axis]
                if not isinstance(text,str) or len(text)>128:
                    raise SceneError('Assembly expressions allow at most 128 characters of text, even for a constant ("0", not 0); got '
                                     +(f'{len(text)} characters' if isinstance(text,str) else shown(text)))
                expression=compile_expression(text,allowed=ASSEMBLY_ALLOWED)
                if expression['cost']>32 or re.search(r'\b[uv]\b',expression['glsl']):
                    raise SceneError(f'Assembly expressions use t/pi only and at most 32 nodes: {shown(text)} uses u or v, or is too long '
                                     f'({expression["cost"]} nodes). u and v belong in a surface position, not in an assembly')
                compiled[field].append(expression['glsl']);cost+=expression['cost']
        vec=lambda values: 'vec3('+','.join(format(float(x),'.9f') for x in values)+')'
        pivot=vec(group['pivot']);scale=vec(group['scale'])
        rotation='vec3('+','.join(compiled['rotation'])+')'
        translation='vec3('+','.join(compiled['translation'])+')'
        block=(f'{{p-={pivot};p*={scale};vec3 a={rotation},c=cos(a),s=sin(a);'
               'p=vec3(p.x,c.x*p.y-s.x*p.z,s.x*p.y+c.x*p.z);'
               'p=vec3(c.y*p.x+s.y*p.z,p.y,-s.y*p.x+c.y*p.z);'
               'p=vec3(c.z*p.x-s.z*p.y,s.z*p.x+c.z*p.y,p.z);'
               f'p+={pivot}+{translation};}}')
        if parent is not None:block+=result[parent]['glsl'];cost+=result[parent]['cost']
        result[identifier]={'glsl':block,'cost':cost,'depth':depth}
    return result
