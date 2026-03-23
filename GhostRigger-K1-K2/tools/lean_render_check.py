#!/usr/bin/env python3
"""
Lean render check - renders a SINGLE model and outputs JSON result to stdout.
Called in a subprocess by the batch audit to avoid memory leaks.

Usage: python3 tools/lean_render_check.py <resref> <game> <size>
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.resources.game_library import GameLibrary
from src.core.mdl_parser import MDLBinaryParser
from src.gui.gpu_renderer import render_model_autoframe
import numpy as np
from PIL import Image

K1_DIR = "game_data/k1_extracted"
K2_DIR = "game_data/k2_extracted"

def score_render(img):
    arr = np.array(img.convert('RGBA'))
    fg_mask = arr[:,:,3] > 10
    total = arr.shape[0] * arr.shape[1]
    fg_count = int(fg_mask.sum())
    if fg_count == 0:
        return {'ok': False, 'issues': ['EMPTY_RENDER'], 'coverage_pct': 0.0}
    fg = arr[fg_mask].astype(float)
    r, g, b = fg[:,0], fg[:,1], fg[:,2]
    yellow = ((r > 160) & (g > 160) & (b < 80) & ((r+g) > 2.5*b.clip(1)))
    pink   = ((r > 180) & (b > 180) & (g < 100))
    white  = ((r > 220) & (g > 220) & (b > 220))
    yp = float(100*yellow.sum()/fg_count)
    pp = float(100*pink.sum()/fg_count)
    wp = float(100*white.sum()/fg_count)
    cp = float(100*fg_count/total)
    issues = []
    if yp > 5.0: issues.append(f'YELLOW:{yp:.1f}%')
    if pp > 5.0: issues.append(f'PINK:{pp:.1f}%')
    if wp > 30.0: issues.append(f'WHITE:{wp:.1f}%')
    if cp < 1.0: issues.append(f'LOW_COV:{cp:.2f}%')
    return {'ok': len(issues)==0, 'issues': issues, 
            'coverage_pct': cp, 'yellow_pct': yp, 'pink_pct': pp, 'white_pct': wp}

def main():
    resref = sys.argv[1]
    game   = sys.argv[2]
    size   = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    out_png = sys.argv[4] if len(sys.argv) > 4 else None
    
    result = {'resref': resref, 'game': game, 'ok': False, 'error': None, 'score': None}
    try:
        lib = GameLibrary()
        lib.scan(K1_DIR, K2_DIR)
        
        models = [m for m in lib.models if m.resref == resref and m.game == game]
        if not models:
            result['error'] = 'NOT_FOUND'
            print(json.dumps(result)); return
        
        entry = models[0]
        mdl, mdx = lib.get_model_data(entry)
        if not mdl:
            result['error'] = 'NO_MDL_DATA'
            print(json.dumps(result)); return
        
        parser = MDLBinaryParser(mdl, mdx or b'')
        model = parser.parse()
        
        textures = {}
        for node in model.all_nodes():
            for attr in ['bitmap','texture','texture0','texture1']:
                val = getattr(node, attr, None)
                if val and val.strip().lower() not in ('null','','none'):
                    name = val.strip().lower()
                    if name not in textures:
                        data = lib.get_texture_data(name, game)
                        if data: textures[name] = data
        
        renders = render_model_autoframe(model, W=size, H=size, textures=textures, views=['front'])
        if not renders:
            result['error'] = 'NO_RENDER'
            print(json.dumps(result)); return
        
        img = renders.get('front', list(renders.values())[0])
        if out_png:
            img.save(out_png)
        
        score = score_render(img)
        result['ok'] = score['ok']
        result['score'] = score
        result['tex_count'] = len(textures)
    except Exception as e:
        result['error'] = str(e)[:200]
    
    print(json.dumps(result))

if __name__ == '__main__':
    main()
