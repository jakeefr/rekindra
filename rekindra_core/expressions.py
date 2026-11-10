"""Compile bounded arithmetic into shader expressions; never evaluate input code."""
import ast
import math
from .scenes import SceneError

FUNCTIONS={'sin':(1,'sin'),'cos':(1,'cos'),'abs':(1,'abs'),'sqrt':(1,'rsqrt'),
           'exp':(1,'rexp'),'min':(2,'min'),'max':(2,'max'),'pow':(2,'rpow'),
           'clamp':(3,'rclamp'),'mix':(3,'rmix')}


ALLOWED=('Allowed: numbers, + - * / and parentheses, the names u v t pi, and '
         +', '.join(f'{name}({",".join("abc"[:arity])})' for name,(arity,_) in FUNCTIONS.items())
         +'. Use pow(a,b) for powers; there is no **, ^, %, tan, floor, comparison or if')


def _echo(source):
    text=''.join(c if c.isprintable() else '?' for c in source.strip())
    return repr(text[:60]+('...' if len(text)>60 else ''))


def _offender(node,names):
    if isinstance(node,ast.Name):
        known=', '.join(sorted(names)) if names else 'none'
        return f"unknown name '{node.id[:24]}' (bindings defined before this point: {known}; material detail expressions cannot use bindings)"
    if isinstance(node,ast.Call):
        called=node.func.id[:24] if isinstance(node.func,ast.Name) else 'a method or attribute'
        return f"unsupported function '{called}'" if not node.keywords else 'keyword arguments are not supported'
    if isinstance(node,ast.BinOp):
        return {'Pow':'** is not supported, use pow(a,b)','Mod':'% is not supported','BitXor':'^ is not supported, use pow(a,b)',
                'FloorDiv':'// is not supported, use /'}.get(type(node.op).__name__,'unsupported operator')
    if isinstance(node,ast.Constant):return 'only numeric constants are supported'
    return {'Compare':'comparisons are not supported, use clamp, min, max or mix','IfExp':'if/else is not supported, use mix or clamp',
            'Attribute':'attributes such as math.sin are not supported, call sin directly'}.get(type(node).__name__,'unsupported syntax')


def compile_expression(source, names=None):
    if not isinstance(source,str):
        raise SceneError('Surface expressions require 1-512 characters: every expression is a string, even a constant '
                         f'("0", not 0; "sin(u*2*pi)"); got {type(source).__name__} {source!r:.40}')
    if not 1<=len(source)<=512:
        raise SceneError(f'Surface expressions require 1-512 characters; got {len(source)}. Move repeated terms into bindings')
    try:tree=ast.parse(source.strip(),mode='eval')
    except (SyntaxError,ValueError,RecursionError) as exc:
        raise SceneError(f'Invalid surface expression {_echo(source)}: write one arithmetic expression. {ALLOWED}') from exc
    cost=0
    def visit(node,depth=0):
        nonlocal cost
        cost+=1
        if cost>128 or depth>24:raise SceneError('Surface expression is too complex')
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>1000 or not math.isfinite(node.value):raise SceneError('Expression constants must be finite and within +/-1000')
            return format(float(node.value),'.9f')
        if isinstance(node,ast.Name):
            if node.id in ('u','v','t','pi'):return node.id
            if names and node.id in names:return names[node.id]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            return ('-' if isinstance(node.op,ast.USub) else '+')+'('+visit(node.operand,depth+1)+')'
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=visit(node.left,depth+1),visit(node.right,depth+1)
            if isinstance(node.op,ast.Div):return f'rdiv({a},{b})'
            op={ast.Add:'+',ast.Sub:'-',ast.Mult:'*'}[type(node.op)]
            return f'bound(({a}){op}({b}))'
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
            arity,name=FUNCTIONS[node.func.id]
            if len(node.args)!=arity:
                raise SceneError(f'Wrong number of math function arguments: {node.func.id} takes {arity}, got {len(node.args)} in {_echo(source)}')
            return f'bound({name}('+','.join(visit(arg,depth+1) for arg in node.args)+'))'
        raise SceneError('Only u, v, t, pi, earlier local bindings, arithmetic and supported math functions are allowed: '
                         f'{_offender(node,names)} in {_echo(source)}. {ALLOWED}')
    glsl=visit(tree.body)
    return {'glsl':glsl,'cost':cost}


def _bound(a):return min(max(a,-10000.0),10000.0)


_SAMPLERS={'sin':math.sin,'cos':math.cos,'abs':abs,
           'sqrt':lambda a:math.sqrt(max(0.0,a)),
           'exp':lambda a:math.exp(min(max(a,-16.0),16.0)),
           'min':min,'max':max,
           'pow':lambda a,b:_bound(min(max(a,.0001),10000.0)**min(max(b,-8.0),8.0)),
           'clamp':lambda a,b,c:min(max(a,min(b,c)),max(b,c)),
           'mix':lambda a,b,c:a+(b-a)*min(max(c,0.0),1.0)}


def _run(node,env):
    if isinstance(node,ast.Constant):return float(node.value)
    if isinstance(node,ast.Name):return env[node.id]
    if isinstance(node,ast.UnaryOp):
        x=_run(node.operand,env);return -x if isinstance(node.op,ast.USub) else x
    if isinstance(node,ast.BinOp):
        a,b=_run(node.left,env),_run(node.right,env)
        if isinstance(node.op,ast.Div):
            return _bound(a/(b if abs(b)>=.0001 else (-.0001 if b<0 else .0001)))
        return _bound(a+b if isinstance(node.op,ast.Add) else a-b if isinstance(node.op,ast.Sub) else a*b)
    return _bound(_SAMPLERS[node.func.id](*[_run(arg,env) for arg in node.args]))


def sampler(source):
    """Return f(u,v,t) mirroring the shader helpers for an already-compiled
    binding-free expression. Walks the parsed tree; never evaluates input code."""
    compile_expression(source)
    body=ast.parse(source.strip(),mode='eval').body
    return lambda u,v,t:_run(body,{'u':u,'v':v,'t':t,'pi':math.pi})


def surface_sampler(position,bindings=()):
    """Return f(u,v,t) giving the position tuple of a surface, evaluating its
    ordered local bindings first. f.cost is the expression nodes one call walks."""
    names={};steps=[];cost=0
    for binding in bindings:
        cost+=compile_expression(binding['expression'],names)['cost']
        steps.append((binding['name'],ast.parse(binding['expression'].strip(),mode='eval').body))
        names[binding['name']]=binding['name']
    bodies=[]
    for source in position:
        cost+=compile_expression(source,names)['cost']
        bodies.append(ast.parse(source.strip(),mode='eval').body)
    def sample(u,v,t):
        env={'u':u,'v':v,'t':t,'pi':math.pi}
        for name,body in steps:env[name]=_run(body,env)
        return tuple(_run(body,env) for body in bodies)
    sample.cost=cost
    return sample
