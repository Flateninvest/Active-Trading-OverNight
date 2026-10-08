"""Small deterministic PDF layout helpers; Revision 10's page order and palette."""
from html import escape
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas

W, H = 595.92, 842.88
LEFT, RIGHT, BOTTOM = 40, 40, 804
WIDTH = W - LEFT - RIGHT
NAVY, TEAL, RUST = '#193650', '#168174', '#b94432'
GREY, LINE, PALE, TAN = '#526171', '#bdcbd8', '#f3f6f8', '#faf3e4'


def clean(text):
    for old, new in [('—', '-'), ('–', '-'), ('−', '-'), ('≥', '>='), ('≤', '<='), ('×', 'x'), ('’', "'"), ('“', '"'), ('”', '"'), ('‑', '-')]:
        text = str(text).replace(old, new)
    return text


def paragraph(text, size=9.15, leading=None, bold=False, color='#202a34', mono=False):
    return Paragraph(clean(text), ParagraphStyle('p', fontName='Courier' if mono else ('Helvetica-Bold' if bold else 'Helvetica'),
                     fontSize=size, leading=leading or size*1.31, textColor=HexColor(color), spaceAfter=0))


class Report:
    def __init__(self, path):
        self.c = canvas.Canvas(str(path), pagesize=(W, H), invariant=1, pageCompression=1)
        self.c.setTitle('Trading the night - Research Report Revision 11')
        self.c.setAuthor('Sondre Flateraaker')
        self.y, self.page = 36, 1
        self.bounds=[]

    def text_at(self, text, x, y, width, size=9.15, color='#202a34', bold=False, leading=None, mono=False):
        p=paragraph(text,size,leading,bold,color,mono)
        _, h=p.wrap(width, H)
        p.drawOn(self.c,x,H-y-h)
        return h

    def text(self, text, size=9.15, gap=7, color='#202a34', bold=False, leading=None):
        h=self.text_at(text,LEFT,self.y,WIDTH,size,color,bold,leading)
        self.y+=h+gap
        return h

    def heading(self, number, title):
        self.y+=6
        self.c.setFillColor(HexColor(NAVY))
        self.c.setFont('Times-Bold',12.1)
        self.c.drawString(LEFT,H-self.y-12,clean(f'{number}  {title}'))
        self.c.setStrokeColor(HexColor(LINE)); self.c.setLineWidth(.55)
        self.c.line(LEFT,H-self.y-19,W-RIGHT,H-self.y-19)
        self.y+=27

    def label(self, text):
        self.text(text,size=7.6,color=GREY,bold=True,gap=6)

    def box(self, title, text, fill=PALE, accent=NAVY, size=9.05):
        p=paragraph(text,size)
        _,h=p.wrap(WIDTH-24,H)
        boxh=h+42
        self.c.setFillColor(HexColor(fill));self.c.rect(LEFT,H-self.y-boxh,WIDTH,boxh,fill=1,stroke=0)
        self.c.setFillColor(HexColor(accent));self.c.rect(LEFT,H-self.y-boxh,2,boxh,fill=1,stroke=0)
        self.text_at(title,LEFT+12,self.y+10,WIDTH-24,7.7,accent,True,mono=True)
        p.drawOn(self.c,LEFT+12,H-self.y-boxh+11)
        self.y+=boxh+9

    def table(self, headers, rows, widths=None, size=8.05):
        widths=widths or [WIDTH/len(headers)]*len(headers)
        data=[[paragraph(str(v),size,bold=True,color=NAVY) for v in headers]]
        data.extend([[paragraph(str(v),size,leading=size*1.25) for v in row] for row in rows])
        t=Table(data,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LINEABOVE',(0,0),(-1,0),.7,HexColor(NAVY)),('LINEBELOW',(0,0),(-1,0),.6,HexColor(LINE)),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor(PALE)]),
            ('LINEBELOW',(0,-1),(-1,-1),.45,HexColor(LINE))]))
        _,h=t.wrap(WIDTH,H)
        t.drawOn(self.c,LEFT,H-self.y-h)
        self.y+=h+8

    def cards(self, cards):
        gap=8; cw=(WIDTH-2*gap)/3; hs=[]
        for title,subtitle,body in cards:
            hs.append(34+paragraph(body,8.25).wrap(cw-18,H)[1])
        height=max(hs)+13
        for i,(title,subtitle,body) in enumerate(cards):
            x=LEFT+i*(cw+gap)
            self.c.setStrokeColor(HexColor(LINE));self.c.setLineWidth(.5)
            self.c.rect(x,H-self.y-height,cw,height,stroke=1,fill=0)
            self.text_at(title,x+9,self.y+8,cw-18,7.3,NAVY,True,mono=True)
            self.text_at(subtitle,x+9,self.y+24,cw-18,9.05,NAVY,True)
            self.text_at(body,x+9,self.y+42,cw-18,8.25)
        self.y+=height+8

    def image(self,path,height=None):
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        with Image.open(path) as im:
            iw,ih=im.size
        height=height or WIDTH*ih/iw
        self.c.drawImage(ImageReader(str(path)),LEFT,H-self.y-height,width=WIDTH,height=height,preserveAspectRatio=True,anchor='c')
        self.y+=height+6

    def end_page(self):
        if self.y>BOTTOM:
            raise ValueError(f'Page {self.page} content reaches {self.y:.1f}; limit {BOTTOM}')
        self.bounds.append({'page':self.page,'content_bottom':round(self.y,1)})
        self.c.setFont('Helvetica',7.3);self.c.setFillColor(HexColor(GREY))
        self.c.drawString(LEFT,19,'eToro Active Trading Track - Research Report Rev 11 - Sondre Flateraaker')
        self.c.drawRightString(W-RIGHT,19,str(self.page))
        self.c.showPage();self.page+=1;self.y=36

    def finish(self):
        self.end_page();self.c.save()
        return self.bounds

    def diagram(self):
        """Retain the original seven-step workflow and the dashed session-252 review."""
        c=self.c;top=self.y
        def box(x,y,w,h,title,body,fill=PALE,stroke=LINE):
            c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(.6)
            c.rect(x,H-y-h,w,h,fill=1,stroke=1)
            self.text_at(title,x+7,y+7,w-14,7.7,NAVY,True)
            self.text_at(body,x+7,y+25,w-14,7.0,leading=9)
        def arrow(x1,y1,x2,y2,color=GREY,dash=False):
            c.setStrokeColor(HexColor(color));c.setFillColor(HexColor(color));c.setLineWidth(.7)
            c.setDash(3,2) if dash else c.setDash()
            c.line(x1,H-y1,x2,H-y2);c.setDash()
            import math
            angle=math.atan2(y2-y1,x2-x1)
            p=c.beginPath();p.moveTo(x2,H-y2)
            for a in [angle+2.6,angle-2.6]:p.lineTo(x2+4*math.cos(a),H-(y2+4*math.sin(a)))
            p.close();c.drawPath(p,fill=1,stroke=0)
        self.text_at('DETERMINISTIC CODE',LEFT,top,300,7.0,NAVY,True,mono=True)
        self.text_at('PROPOSED FROZEN ANALYST PASS',LEFT+344,top,170,6.8,NAVY,True,mono=True)
        w=76;g=8
        specs=[('1  Universe','200 supplied names; daily availability check.'),('2  Night gate','Dispersion above its own expanding median.'),('3  Pool of 30','60-day momentum, known at prior close.'),('4  Roster','Top 10 by 20-session overnight persistence.')]
        for i,(title,body) in enumerate(specs):
            x=LEFT+i*(w+g);box(x,top+18,w,87,title,body)
            if i<3:arrow(x+w,top+61,x+w+g,top+61)
        box(LEFT+344,top+18,WIDTH-344,87,'5  Analyst pass','Read flow + Hidden Angles for these names only. Verify sources, catalyst and falsifier. May remove; never add.',TAN)
        arrow(LEFT+328,top+61,LEFT+344,top+61)
        self.text_at('GATE SHUT: CASH. A pending exit blocks new entries.',LEFT+10,top+113,WIDTH-20,7.6,TEAL,True)
        arrow(LEFT+425,top+105,LEFT+425,top+139)
        box(LEFT,top+139,WIDTH,53,'6  EXECUTE - proposed broker connection','Submit closing orders before the verified cutoff; sell at the next executable open. At most 10% per name, 100% gross. Missing exit: retain and monitor; no new entries.',PALE,NAVY)
        arrow(LEFT+100,top+192,LEFT+100,top+207)
        box(LEFT,top+207,250,69,'7  LOG EACH DECISION AND FILL','Evidence cutoff, source IDs, quoted spread, participation, actual fill versus reference print. No assumed fill is called an observed cost.')
        box(LEFT+260,top+207,117,69,'Daily review','P&L and fill costs. Suspend at 12% drawdown or >13 bp over 20 traded nights.')
        box(LEFT+387,top+207,WIDTH-387,69,'SESSION 252','Review the fixed hypothesis. Log reasons before changing any rule.',TAN)
        arrow(LEFT+250,top+239,LEFT+260,top+239)
        arrow(LEFT+377,top+239,LEFT+387,top+239)
        arrow(W-RIGHT+4,top+239,W-RIGHT+4,top+62,color='#9d7936',dash=True)
        arrow(W-RIGHT+4,top+62,W-RIGHT,top+62,color='#9d7936',dash=True)
        self.y=top+287
