"""Bounded numeric cross-sections compiled to original parametric geometry."""
from .scenes import SceneError, _number


def compile_loft(sections):
    if not isinstance(sections,list) or not 2<=len(sections)<=8:
        raise SceneError('Loft requires 2-8 sections')
    count=None;winding=None;previous=None
    for section in sections:
        if not isinstance(section,dict) or set(section)!={'height','points'}:
            raise SceneError('Loft section requires height and points only')
        height=section['height'];_number(height,-80,80,'loft height')
        if previous is not None and height-previous<.0001:
            raise SceneError('Loft heights must increase by at least 0.0001')
        previous=height;points=section['points']
        if not isinstance(points,list) or not 3<=len(points)<=16 or (count is not None and len(points)!=count):
            raise SceneError('Loft sections need matching 3-16 point rings')
        count=len(points)
        for point in points:
            if not isinstance(point,list) or len(point)!=2:raise SceneError('Loft point needs x,z coordinates')
            for value in point:_number(value,-80,80,'loft point')
        # Every non-edge vertex must be strictly on the same side of each edge.
        # This also rejects repeated vertices, crossings and collinear edges.
        for i,a in enumerate(points):
            b=points[(i+1)%count]
            for j,p in enumerate(points):
                if j in (i,(i+1)%count):continue
                cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
                if abs(cross)<=1.e-8:raise SceneError('Loft rings must be strictly convex and nondegenerate')
                sign=1 if cross>0 else -1
                if winding is None:winding=sign
                if sign!=winding:raise SceneError('Loft rings must be convex with consistent winding')
    number=lambda n:format(float(n),'.9f')
    code=[f'float rk_lu=clamp(u,0.,1.)*{count}.;',
          f'int rk_li=min(int(floor(rk_lu)),{count-1});',
          'float rk_lf=rk_lu-float(rk_li);']
    for i,section in enumerate(sections):
        points=','.join('vec2('+','.join(number(x) for x in p)+')' for p in section['points'])
        code.append(f'vec2 rk_la{i}[{count}]=vec2[{count}]({points});')
        code.append(f'vec2 rk_lr{i}=mix(rk_la{i}[rk_li],rk_la{i}[(rk_li+1)%{count}],rk_lf);')
    vec=lambda i:f'vec3(rk_lr{i}.x,{number(sections[i]["height"])},rk_lr{i}.y)'
    code.append(f'vec3 rk_loft_p={vec(0)};')
    for i in range(1,len(sections)):
        code.append(f'rk_loft_p+=({vec(i)}-{vec(i-1)})*clamp(v*{len(sections)-1}.-{i-1}.,0.,1.);')
    return {'definitions':'\n'.join(code),'names':{'loft_x':'rk_loft_p.x','loft_y':'rk_loft_p.y','loft_z':'rk_loft_p.z'},
            'cost':96+len(sections)*(4*count+32),'ring_points':count,'intervals':len(sections)-1}
