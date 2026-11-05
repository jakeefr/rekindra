"""Compile bounded arithmetic into shader expressions; never evaluate input code."""
import ast
import math
from .scenes import SceneError

FUNCTIONS={'sin':(1,'sin'),'cos':(1,'cos'),'abs':(1,'abs'),'sqrt':(1,'rsqrt'),
           'exp':(1,'rexp'),'min':(2,'min'),'max':(2,'max'),'pow':(2,'rpow'),
           'clamp':(3,'rclamp'),'mix':(3,'rmix')}


def compile_expression(source):
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
        if isinstance(node,ast.Name) and node.id in ('u','v','t','pi'):return node.id
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
        raise SceneError('Only u, v, t, pi, arithmetic and supported math functions are allowed')
    glsl=visit(tree.body)
    return {'glsl':glsl,'cost':cost}
