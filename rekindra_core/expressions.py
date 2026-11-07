"""Compile bounded arithmetic into shader expressions; never evaluate input code."""
import ast
import math
from .scenes import SceneError

FUNCTIONS={'sin':(1,'sin'),'cos':(1,'cos'),'abs':(1,'abs'),'sqrt':(1,'rsqrt'),
           'exp':(1,'rexp'),'min':(2,'min'),'max':(2,'max'),'pow':(2,'rpow'),
           'clamp':(3,'rclamp'),'mix':(3,'rmix')}


def compile_expression(source, names=None):
    if not isinstance(source,str) or not 1<=len(source)<=512:
        raise SceneError('Surface expressions require 1-512 characters')
    try:tree=ast.parse(source.strip(),mode='eval')
    except (SyntaxError,ValueError,RecursionError) as exc:raise SceneError('Invalid surface expression') from exc
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
            if len(node.args)!=arity:raise SceneError('Wrong number of math function arguments')
            return f'bound({name}('+','.join(visit(arg,depth+1) for arg in node.args)+'))'
        raise SceneError('Only u, v, t, pi, earlier local bindings, arithmetic and supported math functions are allowed')
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


def sampler(source):
    """Return f(u,v,t) mirroring the shader helpers for an already-compiled
    binding-free expression. Walks the parsed tree; never evaluates input code."""
    compile_expression(source)
    body=ast.parse(source.strip(),mode='eval').body
    def run(node,env):
        if isinstance(node,ast.Constant):return float(node.value)
        if isinstance(node,ast.Name):return env[node.id]
        if isinstance(node,ast.UnaryOp):
            x=run(node.operand,env);return -x if isinstance(node.op,ast.USub) else x
        if isinstance(node,ast.BinOp):
            a,b=run(node.left,env),run(node.right,env)
            if isinstance(node.op,ast.Div):
                return _bound(a/(b if abs(b)>=.0001 else (-.0001 if b<0 else .0001)))
            return _bound(a+b if isinstance(node.op,ast.Add) else a-b if isinstance(node.op,ast.Sub) else a*b)
        return _bound(_SAMPLERS[node.func.id](*[run(arg,env) for arg in node.args]))
    return lambda u,v,t:run(body,{'u':u,'v':v,'t':t,'pi':math.pi})
