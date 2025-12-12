# IntelliTag  

Image Labelling in Python, with minimal libraries.  


## Installation  

* create `venv` and do `pip install -r requirements.txt` from within.  
* Start: `python label_editor.py`  


## Getting started  

* `W` key toggles drawing mode ON and OFF. Use it for continuos drawing.  
* Left (&#8592;) and right (&#8594;) arrows to navigate between images.  
* `Ctrl+S` to save labels.  
* Select the labels from dropdown menu, which pulls it from local `classes.txt` file in root folder (*`load_classes()`*). If starting from scratch, use the "*Add...*" button.  


Label files are saved as *json* with following format in the same folder as images,  
*`cx, cy, w, h, angle, label`*  

`
"boxes": [  
    {
      "cx": 245.53571428571442,
      "cy": 966.0714285714287,
      "w": 399.64364163798365,
      "h": 137.43719007974215,
      "angle": 27.454011942234928,
      "label": "biscuits"
    },  
    {
      "cx": 517.8571428571427,
      "cy": 791.071428571428,
      "w": 373.3724935072987,
      "h": 118.08807702583634,
      "angle": 21.38727878326027,
      "label": "biscuits"
    },  
`  

*cx*: center x  
*cy*: center y  
*w*: width  
*h*: height  
*angle*: angle in degrees (-90 to +90)  
*label*: category (in text)  

### *Leave a :star:*  if you like it  

_______________ 

