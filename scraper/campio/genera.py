import sys,json,pathlib,subprocess,tempfile,shutil
from playwright.sync_api import sync_playwright
dades=json.loads(sys.argv[1]); sortida=sys.argv[2]; canco=sys.argv[3]
u=pathlib.Path('/home/claude/cbmonforte_jugadors/scraper/campio/plantilla.html').as_uri()
d=pathlib.Path(tempfile.mkdtemp())
init=f"window.DADES={json.dumps(dades,ensure_ascii=False)};"
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":1080,"height":1350}); pg.add_init_script(init); pg.goto(u); pg.wait_for_load_state('networkidle'); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(200)
    pg.screenshot(path=sortida+'.png'); pg.close()
    pg=b.new_page(viewport={"width":1080,"height":1920}); pg.add_init_script(init+"window.REEL=true"); pg.goto(u); pg.wait_for_load_state('networkidle'); pg.evaluate('document.fonts.ready')
    for n in range(300):
        pg.evaluate(f"document.getAnimations().forEach(a=>{{a.pause();a.currentTime={n*1000/30}}})")
        pg.screenshot(path=str(d/f"f{n:04d}.jpg"),type='jpeg',quality=92)
    b.close()
subprocess.run(['ffmpeg','-v','error','-y','-framerate','30','-i',str(d/'f%04d.jpg'),'-i',canco,'-af','afade=t=out:st=8.5:d=1.5','-c:a','aac','-b:a','192k','-c:v','libx264','-pix_fmt','yuv420p','-crf','18','-movflags','+faststart','-t','10',sortida+'_reel.mp4'],check=True)
shutil.rmtree(d)
