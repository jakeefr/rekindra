"""Compile bounded shared rigid frames, independently of surface coordinates."""
import re
from .expressions import compile_expression
from .scenes import SceneError, _number, _LAYER_ID


def compile_assemblies(groups):
    if not isinstance(groups,list) or len(groups)>8:
        raise SceneError('World allows at most eight assemblies')
    result={}
    for group in groups:
        required={'id','translation','rotation','pivot','scale'}
        if not isinstance(group,dict) or set(group) not in (required,required|{'parent'}):
            raise SceneError('Invalid assembly fields')
        identifier=group['id']
        if not isinstance(identifier,str) or not _LAYER_ID.fullmatch(identifier) or identifier in result:
            raise SceneError('Assembly IDs must be unique valid 1-40 character identifiers')
        parent=group.get('parent')
        if 'parent' in group and (not isinstance(parent,str) or parent not in result):
            raise SceneError('Assembly parent must precede its child; no cycles or forward references')
        depth=1+(result[parent]['depth'] if parent is not None else 0)
        if depth>4:raise SceneError('Assembly hierarchy exceeds four levels')
        for field,low,high in [('pivot',-80,80),('scale',.05,8)]:
            values=group[field]
            if not isinstance(values,list) or len(values)!=3:raise SceneError('Assembly '+field+' needs three values')
            for value in values:_number(value,low,high,'assembly '+field)
        compiled={};cost=60  # fixed vector, scale and Euler rotation work per level
        for field in ('translation','rotation'):
            exprs=group[field]
            if not isinstance(exprs,dict) or set(exprs)!={'x','y','z'}:raise SceneError('Assembly transform needs x/y/z expressions')
            compiled[field]=[]
            for axis in ('x','y','z'):
                text=exprs[axis]
                if not isinstance(text,str) or len(text)>128:raise SceneError('Assembly expressions allow at most128 characters')
                expression=compile_expression(text)
                if expression['cost']>32 or re.search(r'\b[uv]\b',expression['glsl']):
                    raise SceneError('Assembly expressions use t/pi only and at most32 nodes')
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
