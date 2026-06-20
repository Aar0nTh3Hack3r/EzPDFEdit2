#!/usr/bin/python3
# PDF Editor Server #

from flask import Flask, send_from_directory, render_template, request, redirect, make_response, abort
from werkzeug.utils import secure_filename
from random import choice, randint
from string import ascii_letters
from threading import Thread
from pdf2image import convert_from_path, convert_from_bytes
from glob import glob
from PyPDF2 import PdfFileWriter, PdfFileReader
import os, json
from shutil import rmtree, copyfile
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.lib.colors import HexColor
from time import sleep, time
import logging

logging.basicConfig(filename='logs', level=logging.DEBUG)

folder = "uploads"
imgs = "images"
out = "output"
back = "backup"
wh = 1000

convert_params = {
    "fmt":'jpeg',
    "dpi":50,
    "thread_count":2,
    "jpegopt":{
        "quality": 50,
        "progressive": True,
        "optimize": True
        },
    "size":wh+1
}


def clear(path, delay=60*60*3):
    sleep(delay)
    logging.debug('Cleared: ' + os.path.basename(path))
    # TODO: Backup
    #rmtree(path)

def randstr(l = 25):
    return ''.join([choice(ascii_letters) for i in range(l)])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() == "pdf"

def patch(num, lns):
    suma = 0
    for i in range(0, len(lns)):
        suma += lns[i]
        if suma > num:
            return (i, num-(suma-lns[i]))
        elif suma == num:
            return (i+1, num-suma)
    return None

def process(Id):
    path = os.path.join(folder, Id)
    files = glob(path + '/*.pdf')
    Len = len(files)
    imgsPath = os.path.join(path, imgs)
    num = 0
    for i in range(Len):
        logging.debug(files[i])
        PDFimg = convert_from_path(files[i],
                                    **convert_params
                                    )
        for img in PDFimg:
            x, y = img.size
            sz = (int(wh*x/y), wh) if x < y else (wh, int(wh*y/x))
            img.resize(sz).save(os.path.join(imgsPath, str(num)+".jpg")) #.resize(sz)
            num += 1
        with open(os.path.join(path, "done.txt"), 'wt') as o:
            o.write(str(round((i+1)*100/Len,1)))
            o.close()
    Thread(target=clear, args=(path,)).start()

# Autorun
if os.path.isdir(folder):
    for item in os.scandir(folder):
        if os.path.isdir(item):
            clear(item, 0)
        else:
            os.remove(item)

registerFont(TTFont("Inconsolata-ExtraLight","static/Inconsolata/ExtraLight.ttf"))
registerFont(TTFont("Inconsolata-Light","static/Inconsolata/Light.ttf"))
registerFont(TTFont("Inconsolata-Regular","static/Inconsolata/Regular.ttf"))
registerFont(TTFont("Inconsolata-Medium","static/Inconsolata/Medium.ttf"))
registerFont(TTFont("Inconsolata-Bold","static/Inconsolata/Bold.ttf"))
registerFont(TTFont("Inconsolata-SemiBold","static/Inconsolata/SemiBold.ttf"))
registerFont(TTFont("Inconsolata-ExtraBold","static/Inconsolata/ExtraBold.ttf"))
registerFont(TTFont("Inconsolata-Black","static/Inconsolata/Black.ttf"))

app = Flask(__name__)

@app.errorhandler(500)
def servererror(err):
    res = make_response(json.dumps({'error': -1}), 500)
    return res

@app.route('/static/<path:path>/')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/favicon.ico')
def icon():
    return send_from_directory('static', 'favicon.ico')

@app.route('/upload', methods=['POST'])
def upload():
    ufilenr = 0
    files = request.files.getlist("upload[]")
    if len(files) == 0:
        return json.dumps({'error':1})
    rnd = randstr(randint(5,25))
    path = os.path.join(folder, rnd)
    if os.path.isdir(path):
        rmtree(path)
    os.mkdir(path)
    os.mkdir(os.path.join(path, out))
    os.mkdir(os.path.join(path, imgs))
    #logging.debug("upload: " + str(len(files)))
    for file in files:
        if file and allowed_file(file.filename):
            ufilenr += 1
            filename = secure_filename(file.filename)
            file.save(os.path.join(path, filename))
            logging.debug(filename)
        else:
            logging.debug("error: " + file.filename)
            continue
    if ufilenr == 0:
        rmtree(path)
        return json.dumps({'error':1})
    with open(os.path.join(path, "done.txt"), 'wt') as o:
        o.write("0.0")
        o.close()
    Thread(target=process, args=(rnd,)).start()
    return json.dumps({'error': 0, 'id': rnd})
        
@app.route('/project/<Id>/')
def project(Id):
    #logging.debug(ids)
    try:
        with open(os.path.join(folder, Id, 'done.txt'), 'rt') as o:
            d = o.read()
            o.close()
        if float(d) == 100:
            return render_template("editor.html", num=len(glob(os.path.join(folder, Id, imgs)+'/*.jpg')))
    except:
        return redirect("/")
    page = make_response(render_template("loading.html", done=d))
    page.headers["refresh"] = "1"
    return page

@app.route('/project/<Id>/<Img>/')
def image(Id, Img):
    if not os.path.isdir(os.path.join(folder, Id)) or not Img.endswith('.jpg'):
        return redirect("/")
    #logging.debug(os.path.join(Id, imgs, Img))
    return send_from_directory(os.path.join(folder, Id, imgs), Img)

@app.route('/edit/<Id>/<Img>/')
def editimage(Id, Img):
    if not os.path.isdir(os.path.join(folder, Id)):
        return redirect("/")
    #logging.debug(os.path.join(Id, imgs, Img))
    return render_template("editor2.html")

@app.route('/project/<Id>/restore', methods=['POST'])
def restore(Id):
    path = os.path.join(folder, Id)
    images = os.path.join(path, imgs)
    bPdfs = os.path.join(path, back)
    bImgs = os.path.join(images, back)
    
    if not os.path.isdir(path):
        return json.dumps({'error': 1})
    with open(os.path.join(path, 'done.txt')) as o:
        num = float(o.read())
        o.close()
    if num != 100:
        return json.dumps({'error': 3})

    if os.path.isdir(bPdfs):
        files = glob(os.path.join(bPdfs, '*.pdf'))
        for file in files:
            copyfile(file, os.path.join(path, os.path.basename(file)))
        rmtree(bPdfs)
    if os.path.isdir(bImgs):
        files = glob(os.path.join(bImgs, '*.jpg'))
        for file in files:
            copyfile(file, os.path.join(images, os.path.basename(file)))
        rmtree(bImgs)

    return json.dumps({'error': 0})

@app.route('/project/<Id>/<Img>/rotate', methods=['POST'])
def rotate(Id, Img):
    path = os.path.join(folder, Id)
    images = os.path.join(path, imgs)
    img = os.path.join(images, Img)
    bPdfs = os.path.join(path, back)
    bImgs = os.path.join(images, back)
    if not request.is_json or not os.path.isdir(path) or not os.path.isfile(img) or not Img.endswith('.jpg'):
        return json.dumps({'error': 1})
    with open(os.path.join(path, 'done.txt')) as o:
        num = float(o.read())
        o.close()
    if num != 100:
        return json.dumps({'error': 3})

    data = request.get_json()
    if len(data) != 1:
        return json.dumps({'error': 5})
    direct = data[0]
    if direct != 1 and direct != 2:
        return json.dumps({'error': 6})
    
    num = int(Img.replace('.jpg', ''))

    pdfs = glob(os.path.join(path, '*.pdf'))
    suma = 0
    got = -1
    for fname in pdfs:
        existing_pdf = PdfFileReader(open(fname, "rb"))
        pgc = existing_pdf.getNumPages()
        suma += pgc
        if suma > num:
            got = num - (suma - pgc)
            break
        else:
            existing_pdf.stream.close()
    if got == -1:
        return json.dumps({'error': 4})

    bPdf = os.path.join(bPdfs, os.path.basename(fname))
    bImg = os.path.join(bImgs, Img)
    if not os.path.isdir(bPdfs):
        os.mkdir(bPdfs)
    if not os.path.isdir(bImgs):
        os.mkdir(bImgs)
    if not os.path.isfile(bPdf):
        copyfile(fname, bPdf)
    if not os.path.isfile(bImg):
        copyfile(img, bImg)

    #return json.dumps(request.get_json())

    page = existing_pdf.getPage(got)

    if direct == 1:
        page.rotateClockwise(90)
    else:
        page.rotateCounterClockwise(90)

    onepgpdf = BytesIO()
    forImg = PdfFileWriter()
    forImg.addPage(page)
    forImg.write(onepgpdf)
    onepgpdf.seek(0)
    pdfimg = convert_from_bytes(onepgpdf.read(),
                                **convert_params,
                                single_file=True
                                )
    x, y = pdfimg[0].size
    sz = (int(wh*x/y), wh) if x < y else (wh, int(wh*y/x))
    pdfimg[0].resize(sz).save(img) #.resize(sz)

    output = PdfFileWriter()
    for i in range(pgc):
        if i == got:
            output.addPage(page)
        else:
            output.addPage(existing_pdf.getPage(i))

    outputStream = BytesIO()
    output.write(outputStream)
    outputStream.seek(0)
    existing_pdf.stream.close()
    with open(fname, 'wb') as h:
        h.write(outputStream.read())
        h.close()
    outputStream.close()
    onepgpdf.close()

    return json.dumps({'error': 0})

@app.route('/edit/<Id>/<Img>/export', methods=['POST'])
def save(Id, Img):
    path = os.path.join(folder, Id)
    images = os.path.join(path, imgs)
    img = os.path.join(images, Img)
    bPdfs = os.path.join(path, back)
    bImgs = os.path.join(images, back)
    if not request.is_json or not os.path.isdir(path) or not os.path.isfile(img) or not Img.endswith('.jpg'):
        return json.dumps({'error': 1})
    with open(os.path.join(path, 'done.txt')) as o:
        num = float(o.read())
        o.close()
    if num != 100:
        return json.dumps({'error': 3})

    data = request.get_json()
    logging.debug(json.dumps(data))
    if len(data) == 0:
        return json.dumps({'error': 0})
    
    num = int(Img.replace('.jpg', ''))

    pdfs = glob(os.path.join(path, '*.pdf'))
    suma = 0
    got = -1
    for fname in pdfs:
        existing_pdf = PdfFileReader(open(fname, "rb"))
        pgc = existing_pdf.getNumPages()
        suma += pgc
        if suma > num:
            got = num - (suma - pgc)
            break
        else:
            existing_pdf.stream.close()
    if got == -1:
        return json.dumps({'error': 4})

    bPdf = os.path.join(bPdfs, os.path.basename(fname))
    bImg = os.path.join(bImgs, Img)
    if not os.path.isdir(bPdfs):
        os.mkdir(bPdfs)
    if not os.path.isdir(bImgs):
        os.mkdir(bImgs)
    if not os.path.isfile(bPdf):
        copyfile(fname, bPdf)
    if not os.path.isfile(bImg):
        copyfile(img, bImg)

    #return json.dumps(request.get_json())

    page = existing_pdf.getPage(got)
    rot = page.get('/Rotate')
    rot = rot if rot else 0 # not None
    rot %= 360
    #logging.debug(str(rot))
    packet = BytesIO()
    
    width  = float(page.mediaBox.getWidth())# if rot % 180 == 0 else page.mediaBox.getHeight()
    height = float(page.mediaBox.getHeight())# if rot % 180 == 0 else page.mediaBox.getWidth()
    
    portrait = width < height # if rot == 0 or rot == 180 else width > height
    constant = height / wh if portrait else width / wh
    #sz = (int(wh*width/height), wh) if portrait else (wh, int(wh*height/width))
    can = Canvas(packet, pagesize=(width, height))
    can.rotate(rot)

    for textinfo in data:
        text, posX, posY, fontSize, font, textColor = textinfo
        fontSize *= constant
        a, b = fontSize/2*len(text), fontSize/1.25 # w, h
        posX *= constant
        posY *= constant
        
        if rot == 0:
            posY = height - posY - b
        elif rot == 90:
            posY = -b - posY
        elif rot == 180:
            posY = -b - posY
            posX += -width
        elif rot == 270:
            posY = width - b - posY
            posX -= height

        can.setFillColorRGB(255,255,255)
        can.rect(posX, posY, a, b, 0, 1)
        
        txtobj = can.beginText(posX,posY+3)
        txtobj.setFillColor(HexColor(textColor))
        txtobj.setFont(font, fontSize)
        txtobj.textLine(text)
        can.drawText(txtobj)
        
    can.save()
    packet.seek(0)
    new_pdf = PdfFileReader(packet)
    txtpg = new_pdf.getPage(0)
    #txtpg.rotateClockwise(page.get('/Rotate'))
    page.mergePage(txtpg)

    onepgpdf = BytesIO()
    forImg = PdfFileWriter()
    forImg.addPage(page)
    forImg.write(onepgpdf)
    onepgpdf.seek(0)
    pdfimg = convert_from_bytes(onepgpdf.read(),
                                **convert_params,
                                single_file=True
                                )
    x, y = pdfimg[0].size
    sz = (int(wh*x/y), wh) if x < y else (wh, int(wh*y/x))
    pdfimg[0].resize(sz).save(img) #.resize(sz)

    output = PdfFileWriter()
    for i in range(pgc):
        if i == got:
            output.addPage(page)
        else:
            output.addPage(existing_pdf.getPage(i))

    outputStream = BytesIO()
    output.write(outputStream)
    outputStream.seek(0)
    existing_pdf.stream.close()
    with open(fname, 'wb') as h:
        h.write(outputStream.read())
        h.close()
    outputStream.close()
    packet.close()
    onepgpdf.close()

    return json.dumps({'error': 0})

@app.route('/project/<Id>/export')
def export(Id):
    try:
        with open(os.path.join(folder, Id, 'done.txt'), 'rt') as o:
            d = o.read()
            o.close()
        if float(d) != 100:
            return redirect(f"/project/{Id}/")
    except:
        logging.debug("export failed, ID=" + Id)
        abort(404)
        
    data = request.args.get('data')
    logging.debug(data)
    if data == None or data == '':
        return "Data arg is missing."
    nums_s = data.split('-')
    nums = []
    for i in nums_s:
        nums.append(int(i))
    inputpdf = []
    lns = []
    path = os.path.join(folder, Id)
    files = glob(path+'/*.pdf')
    for i in range(len(files)):
        logging.debug(files[i])
        inputpdf.append( PdfFileReader(open(files[i], "rb")) )
        lns.append(inputpdf[i].getNumPages())
    writer = PdfFileWriter()
    for i in nums:
        val = patch(i, lns)
        writer.addPage(inputpdf[val[0]].getPage(val[1]))
    pdfname = 'output.pdf'
    with open(os.path.join(path, out, pdfname), 'wb') as outfile:
        writer.write(outfile)
        outfile.close()
    for i in inputpdf:
        i.stream.close()
    ret = send_from_directory(os.path.join(path, out), pdfname)
    ret.headers["Content-Disposition"] = f"inline; filename=Output_{time()}_EzPdfEdit.pdf"
    return ret

#app.debug = True

#tohttps = Flask(__name__)
#@tohttps.route('/', defaults={'path': ''})
#@tohttps.route('/<path:path>')
#def catch_all(path):
#	return redirect('https://barthaaron.go.ro/' + path)
#def server2():
#	tohttps.run("192.168.88.21", 8080)

#Thread(target=server2).start()
#app.run("192.168.88.21", 4430, ssl_context=('./cert/signed_chain.crt', './cert/domain.key'))
app.run("0.0.0.0", 2000)

