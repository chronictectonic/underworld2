##~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~##
##                                                                                   ##
##  This file forms part of the Underworld geophysics modelling application.         ##
##                                                                                   ##
##  For full license and copyright information, please refer to the LICENSE.md file  ##
##  located at the project root, or contact the authors.                             ##
##                                                                                   ##
##~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~##


import underworld as uw
import errno
import underworld._stgermain as _stgermain
import os
import urllib2
import time
import json
from base64 import b64encode
import libUnderworld
import subprocess
from subprocess import Popen, PIPE, STDOUT
from . import objects
import libUnderworld as _libUnderworld
import sys
import os

#Attempt to import lavavu module
lavavu = None
try:
    import lavavu
    sys.path.append(os.path.dirname(lavavu.__file__))
except:
    print "LavaVu module not found! disabling inline visualisation"

# lets create somewhere to dump data for this session
try:
    tmpdir = os.environ['TMPDIR']
except:
    tmpdir = "/tmp"
os.path.join(tmpdir,"glucifer")
try:
    os.makedirs(tmpdir)
except OSError as exception:
    if exception.errno != errno.EEXIST:
        raise

class Store(_stgermain.StgCompoundComponent):
    """  
    The Store class provides a database which stores gLucifer drawing objects
    as they are rendered in figures. It also provides associated routines for saving
    and reloading this database to external files
    
    In addition to parameter specification below, see property docstrings for
    further information.

    Parameters
    ----------
    filename: str
        Filename to use for a disk database, default is in memory only unless saved.
    split: bool
        Set to true to write a separate database file for each timestep visualised
    view: bool
        Set to true and pass filename if loading a saved database for revisualisation
            
    Example
    -------
        
    Create a database:
    
    >>> import glucifer
    >>> store = glucifer.Store()

    Optionally provide a filename so you don't need to call save later (no extension)
    
    >>> store = glucifer.Store('myvis')

    Pass to figures when creating them
    (Providing a name allows you to revisualise the figure from the name)
    
    >>> fig = glucifer.Figure(store, name="myfigure")
    
    When figures are rendered with show() or save(imgname), they are saved to storage
    If you don't need to render an image but still want to store the figure to view later,
    just call save() without a filename
    
    >>> fig.save()
    
    Save the database (only necessary if no filename provided when created)
    
    >>> dbfile = store.save("myvis")

    """
    _objectsDict = { "_db":"lucDatabase" }
    _selfObjectName = "_db"
    viewer = None

    def __init__(self, filename=None, split=False, view=False, **kwargs):

        self.step = 0
        if filename and not filename.lower().endswith('.gldb') and not filename.lower().endswith('.db'):
            filename += ".gldb"
        self.filename = filename
        self._objects = []
        self._viewonly = False
        #Don't split on timestep unless filename provided
        if not self.filename: split = False
        self._split = split

        #Open an existing db?
        if view and filename and os.path.isfile(filename):
            self._viewonly = True

        super(Store,self).__init__(**kwargs)

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        # append random string to provided name to ensure unique component names
        # call parents method
        super(Store,self)._add_to_stg_dict(componentDictionary)

        #Extension needs to added by lucDatabase when generating per timestep files
        filename = self.filename
        if filename:
            #Need base name, strip extensions if provided
            if filename.lower().endswith('.gldb'):
                filename = filename[0:-5]
            if filename.lower().endswith('.db'):
                filename = filename[0:-3]

        componentDictionary[self._db.name].update( {
                            "filename"          :filename,
                            "splitTransactions" :True,
                            "singleFile"        :not self._split,
                            "viewonly"          :self._viewonly
        } )

    def _setup(self):
        # Detect if viewer was built by finding executable...
        # (even though no longer needed as using libLavaVu 
        #  will keep this for now as is useful to know if the executable was built
        #  and to pass it as first command line arg or if needed to get html path)
        self._lvpath = self._db.bin_path
        self._lvbin = os.path.join(self._db.bin_path, "LavaVu")
        global lavavu
        if lavavu and not os.path.isfile(self._lvbin):
            print("LavaVu rendering engine does not appear to exist. Perhaps it was not compiled.\n"
                  "Please check your configuration, or contact developers.")
            lavavu = None

    def save(self,filename):
        """  
        Saves the database to the provided filename.
            
        Parameters
        ----------
        filename :str
            Filename to save file to.  May include an absolute or relative path.
        """
        if uw.rank() == 0:
            if not isinstance(filename, str):
                raise TypeError("Provided parameter 'filename' must be of type 'str'. ")
            if not filename.lower().endswith('.gldb') and not filename.lower().endswith('.db'):
                filename += '.gldb'
            libUnderworld.gLucifer.lucDatabase_BackupDbFile(self._db, filename)
            return filename

    def lvrun(self, db=None, *args, **kwargs):
        if not db:
            db = self._db.path
        #Use a single LavaVu instance per db(store) to save resources
        if not self.viewer:
            self.viewer = lavavu.Viewer(cache=False, binpath=self._lvpath, database=db, timestep=self.step, *args, **kwargs)
        else:
            self.viewer.setup(cache=False, database=db, timestep=self.step, *args, **kwargs)

        return self.viewer

    def _generate(self, figname, objects, props):
        #First merge object list with active
        for obj in objects:
            #Add nested colourbar objects
            if obj._colourBar:
                objects.append(obj._colourBar)
                obj._colourBar.parent = obj #Save parent ref

            #Set default parent flag
            obj.parent = None

            #Add to stored object list if not present
            if obj not in self._objects:
                self._objects.append(obj)

        #Set default names on objects where omitted by user
        #Needs to be updated every time as indices may have changed
        for o in range(len(self._objects)):
            #Default name + idx if no user set name
            obj = self._objects[o]
            if not "name" in obj.properties:
                if obj.properties.get("colourbar"):
                   obj.properties["name"] = 'ColourBar_' + str(o)
                else:
                   obj.properties["name"] = obj._dr.type[3:] + '_' + str(o)

        if not self._viewonly:
            #Set the write step
            self._db.timeStep = self.step

            #Delete all drawing objects in register
            for ii in range(self._db.drawingObjects.objects.count,0,-1):
                libUnderworld.StGermain._Stg_ObjectList_RemoveByIndex(self._db.drawingObjects.objects,ii-1, libUnderworld.StGermain.KEEP)

            #Add drawing objects to register and output any custom data on them
            for obj in self._objects:
                #Hide objects not in this figure (also check parent for colour bars)
                obj.properties["visible"] = bool(obj in objects or obj.parent and obj.parent in objects)

                #Ensure properties updated before object written to db
                _libUnderworld.gLucifer.lucDrawingObject_SetProperties(obj._dr, obj._getProperties());
                if obj.colourMap:
                    _libUnderworld.gLucifer.lucColourMap_SetProperties(obj.colourMap._cm, obj.colourMap._getProperties());

                #Add the object to the drawing object register for the database
                libUnderworld.StGermain.Stg_ObjectList_Append(self._db.drawingObjects.objects,obj._cself)

            # go ahead and fill db
            libUnderworld.gLucifer._lucDatabase_Execute(self._db,None)

            #Write visualisation state as json data
            libUnderworld.gLucifer.lucDatabase_WriteState(self._db, figname, self._get_state(self._objects, props))

            #Output any custom geometry on objects
            if lavavu and uw.rank() == 0:
                lv = self.lvrun() #Open the viewer
                for obj in self._objects:
                    #Create/Transform geometry by object
                    obj.render(lv)
        else:
            #Open db, get state and update it to match active figure
            states = self._read_state()
            #Find state matching figure by name
            found = False
            for state in states:
                if state["figure"] == figname:
                    found = True
                    break
            if not found:
                state = states[-1]

            if len(objects):
                #For each obj in db, lookup in local list by name, replace properties if found
                #if not found locally, objects in db are hidden from view
                for dbobj in state["objects"]:
                    dbobj["visible"] = False
                    for obj in objects:
                        if dbobj["name"] == obj.properties["name"]:
                            #Merge/replace
                            dbobj.update(obj.properties)
                            dbobj["visible"] = True
            else:
                #No objects passed in with figure, simply plot them all
                for obj in state["objects"]:
                    obj["visible"] = True

            export = dict()
            #Global properties passed from figure
            state["properties"].update(props)
            #View properties passed from figure
            #state["views"][0].update(viewprops)
            state["views"][0].update(props)
            #Write updated visualisation state as json data
            libUnderworld.gLucifer.lucDatabase_WriteState(self._db, figname, json.dumps(state, indent=2))

    def _get_state(self, objects, props):
        #Get current state as string for export
        export = dict()
        #Global properties passed from figure
        export["properties"] = props
        #View properties passed from figure
        export["views"] = [props] #[viewprops]
        #Objects passed from figure
        objlist = []
        for obj in objects:
            objlist.append(obj.properties)

        export["objects"] = objlist
        #TODO: ColourMap properties

        return json.dumps(export, indent=2)

    def _read_state(self):
        #Read state from database
        global lavavu
        if not lavavu or uw.rank() > 0:
            return
        if not self._db.db:
            libUnderworld.gLucifer.lucDatabase_OpenDatabase(self._db)
        try:
            lv = self.lvrun()
            #Get state, includes the list of objects in the loaded database
            statestr = lv.getFigures()
            #Also save the step data
            self.timesteps = json.loads(lv.getTimeSteps())
            return json.loads(statestr)
        except RuntimeError,e:
            print "LavaVu error: " + str(e)
            import traceback
            traceback.print_exc()
            pass

    def empty(self):
        """    Empties all the cached drawing objects
        """
        self._objects = []

class Figure(dict):
    """  
    The Figure class provides a window within which gLucifer drawing objects
    may be rendered. It also provides associated routines for image generation
    and visualisation.
    
    In addition to parameter specification below, see property docstrings for
    further information.

    Parameters
    ----------
    store: glucifer.Store
        Database to collect visualisation data, this may be shared among figures
        to collect their data into a single file.
    name: str
        Name of this figure, optional, used for revisualisation of stored figures.
    resolution: tuple
        Image resolution provided as a tuple.
    boundingBox: tuple
        Tuple of coordinate tuples defining figure bounding box.
        For example ( (0.1,0.1), (0.9,0.9) )
    facecolour: str
        Background colour for figure.
    edgecolour: str
        Edge colour for figure.
    title: str
        Figure title.
    axis: bool
        Bool to determine if figure axis should be drawn.
    quality: unsigned
        Antialiasing oversampling quality. For a value of 2, the image will be
        rendered at twice the resolution, and then downsampled. Setting
        this to 1 disables antialiasing, values higher than 3 are not recommended..
    properties: str
        Further properties to set on the figure.
            
    Example
    -------
        
    Create a figure:
    
    >>> import glucifer
    >>> fig = glucifer.Figure()

    We need a mesh
    
    >>> import underworld as uw
    >>> mesh = uw.mesh.FeMesh_Cartesian()

    Add drawing objects:
    
    >>> fig.append( glucifer.objects.Surface( mesh, 1.) )

    Draw image (note, in a Jupyter notebook, this will render the image within the notebook).
    
    >>> fig.show()
    <IPython.core.display.HTML object>
    
    Save the image
    
    >>> imgfile = fig.save("test_image")

    Clean up:
    
    >>> if imgfile: 
    ...     import os; 
    ...     os.remove( imgfile )

    """
    _viewerProc = None
    _id = 1

    def __init__(self, store=None, name=None, figsize=None, boundingBox=None, facecolour="white",
                 edgecolour="black", title="", axis=False, quality=1, *args, **kwargs):

        #Create a default database just for this figure if none provided
        if store and isinstance(store, Store):
            self.db = store
        else:
            self.db = Store()

        if name:
            if not isinstance(name,str):
                raise TypeError("'name' object passed in must be of python type 'str'")
        elif "name" in kwargs:
            name = kwargs["name"]
        else:
            name = "Figure_" + str(Figure._id)
            Figure._id += 1
        self.name = name

        if boundingBox and not isinstance(boundingBox,tuple):
            raise TypeError("'boundingBox' object passed in must be of type 'tuple'")
        if boundingBox and not isinstance(boundingBox[0],tuple):
            raise TypeError("'boundingBox[0]' object passed in must be of type 'tuple'")
        if boundingBox and not isinstance(boundingBox[1],tuple):
            raise TypeError("'boundingBox[1]' object passed in must be of type 'tuple'")

        if not isinstance(edgecolour,str):
            raise TypeError("'edgecolour' object passed in must be of python type 'str'")

        if not isinstance(axis,bool):
            raise TypeError("'axis' object passed in must be of python type 'bool'")

        if quality and not isinstance(quality,(int,float)):
            raise TypeError("'quality' object passed in must be of python type 'float' or 'int'")
        self["quality"]=quality

        #Setup default properties
        self.update({"resolution" : (640, 480), "title" : str(title), 
            "axis" : axis, "axislength" : 0.2, "antialias" : True, 
            "background" : facecolour, "margin" : 34, 
            "border" : (1 if edgecolour else 0), "bordercolour" : edgecolour, 
            "rulers" : False, "zoomstep" : 0})

        #User-defined props in kwargs
        self.update(kwargs)
        dict((k.lower(), v) for k, v in self.iteritems())

        if boundingBox:
            #Add 3rd dimension if missing
            if len(boundingBox[0]) < 3 or len(boundingBox[1]) < 3:
                boundingBox = (tuple(list(boundingBox[0]) + [0]), tuple(list(boundingBox[1]) + [0]))
            self["min"] = boundingBox[0]
            self["max"] = boundingBox[1]

        #Legacy parameter
        if figsize and not isinstance(figsize,tuple):
            raise TypeError("'resolution' object passed in must be of python type 'tuple'")
        elif figsize:
            self["resolution"] = figsize
        
        self.draw = objects.Drawing()
        self._drawingObjects = []
        self._script = []

        #Save types of all Drawing derived classes
        def all_subclasses(cls):
            return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in all_subclasses(s)]
        self._object_types = all_subclasses(objects.Drawing)

        super(Figure, self).__init__(*args)

    def __del__(self):
        self.close_viewer()

    def _getProperties(self):
        #Convert properties to string
        return '\n'.join(['%s=%s' % (k,v) for k,v in self.iteritems()]);

    def _setProperties(self, newProps):
        #Update the properties values (merge)
        #values of any existing keys are replaced
        self.update(newProps)

    #Undefined methods call Drawing() constructors if defined, and append to figure
    def __getattr__(self, key):
        #__getattr__ called if no attrib/method found
        def any_method(*args, **kwargs):
            #Find if class exists that extends Drawing
            method = getattr(objects, key)
            if isinstance(method, type) and method in self._object_types:
                #Return the new object and add it to the figure
                newobj = method(*args, **kwargs)
                self.append(newobj)
                return newobj

        return any_method

    @property
    def resolution(self):
        """    resolution (tuple(int,int)): size of window in pixels.
        """
        return self["resolution"]

    @property
    def facecolour(self):
        """    facecolour : colour of face background.
        """
        return self["background"]

    @property
    def edgecolour(self):
        """    edgecolour : colour of figure border.
        """
        return self["bordercolour"]

    @property
    def title(self):
        """    title : a title for the image.
        """
        return self["title"]

    @property
    def axis(self):
        """    axis : Axis enabled if true.
        """
        return self["axis"]

    @property
    def objects(self):
        """    objects : list of objects to be drawn within the figure.
        """
        return self._drawingObjects

    @property
    def properties(self):
        """    
        properties (dict): visual properties of viewport, passed to LavaVu to control 
        rendering output of figure.
        
        When using the property setter, new properties are set, overwriting any duplicate 
        keys but keeping existing values otherwise.
        """
        return self
    @properties.setter
    def properties(self, value):
        self._setProperties(value)

    def show(self, type="Image"):
        """    
        Shows the generated image inline within an ipython notebook.
        
        Parameters
        ----------
        type: str
            Type of visualisation to display ('Image' or 'WebGL').
        
        If IPython is installed, displays the result image or WebGL content inline

        If IPython is not installed, this method will call the default image/web 
        output routines to save the result with a default filename in the current directory

        """
        try:
            if __IPYTHON__:
                self._generate_DB()
                global lavavu
                if not lavavu or uw.rank() > 0:
                    return
                from IPython.display import display,Image,HTML
                if type.lower() == "webgl":
                    display(self._generate_HTML())
                else:
                    #Return inline image result
                    filename = self._generate_image()
                    display(HTML("<img src='%s'>" % filename))
            else:
                #Fallback to export image
                self.save(filename=self.name, type=type)

        except NameError, ImportError:
            #Fallback to export image
            self.save(filename=self.name, type=type)
            pass
        except RuntimeError, e:
            print "Error creating image: "
            print e
            pass
        except:
            raise

    def save_image(self, filename="", size=(0,0)):
        # For back compatibility
        return self.save(filename, size)

    def save_database(self, filename, regen=True):
        if regen:
            self._generate_DB()
        return self.db.save(filename)

    def save(self, filename=None, size=(0,0), type="Image"):
        """  
        Saves the generated image to the provided filename or the figure to the database.
        
        Parameters
        ----------
        filename :str
            Filename to save file to.  May include an absolute or relative path.
        size (tuple(int,int)): size of image in pixels, defaults to original figsize setting
            If omitted, simply saves the figure data without generating an image
        type: str
            Type of visualisation to save ('Image' or 'WebGL').
            
        Returns
        -------
        filename: str
            The final filename (including extension) used to save the image will be returned. Note
            that only the root process will return this filename. All other processes will not return
            anything.
        """
        self._generate_DB()
        global lavavu
        if filename is None or not lavavu or uw.rank() > 0:
            return
        if not isinstance(filename, str):
            raise TypeError("Provided parameter 'filename' must be of type 'str'. ")
        if size and not isinstance(size,tuple):
            raise TypeError("'size' object passed in must be of python type 'tuple'")

        try:
            if type.lower() == "webgl":
                lv = self.db.lvrun()
                return lv.web(True)
            else:
                return self._generate_image(filename, size)
        except RuntimeError,e:
            print "LavaVu error: " + str(e)
            import traceback
            traceback.print_exc()
            pass

    def _generate_DB(self):
        objects = self._drawingObjects[:]
        #Only add default object if used
        if len(self.draw.vertices) > 0:
            objects.append(self.draw)
        self.db._generate(self.name, objects, self)

    def _generate_image(self, filename="", size=(0,0)):
        global lavavu
        if not lavavu or uw.rank() > 0:
            return
        try:
            #Render with viewer
            lv = self.db.lvrun(quality=self["quality"], script=self._script)
            imagestr = lv.image(filename, resolution=size)
            #Return the generated filename
            return imagestr
        except RuntimeError,e:
            print "LavaVu error: " + str(e)
            import traceback
            traceback.print_exc()
            pass
        return ""

    def _generate_HTML(self):
        global lavavu
        if not lavavu or uw.rank() > 0:
            return
        try:
            #Export encoded json string
            lv = self.db.lvrun(script=self._script)
            #Create link to web content directory
            if not os.path.isdir("html"):
                os.symlink(os.path.join(self.db._lvpath, 'html'), 'html')
            jsonstr = lv.web()
            #Write files to disk first, can be passed directly on url but is slow for large datasets
            filename = "input_" + self.db._db.name + ".json"
            text_file = open("html/" + filename, "w")
            text_file.write(jsonstr);
            text_file.close()
            from IPython.display import IFrame
            return IFrame("html/index.html#" + filename, width=self["resolution"][0], height=self["resolution"][1])
            #import base64
            #return IFrame("html/index.html#" + base64.b64encode(jsonstr), width=self["resolution"][0], height=self["resolution"][1])
        except RuntimeError,e:
            print "LavaVu error: " + str(e)
            import traceback
            traceback.print_exc()
            pass
        return ""

    def script(self, cmd=None):
        """ 
        Append to or get contents of the saved script.
        
        Parameters
        ----------
        cmd: str
            Command to add to script.
        """
        if cmd:
            if isinstance(cmd, list):
                self._script += cmd
            else:
                self._script += [cmd]
        else:
            self._script = []
        #Returns contents as newline separated string
        return '\n'.join(self._script)

    def lv(self):
        """ Return active viewer instance
        """
        return self.db.viewer

    def viewer(self):
        """ Open the inline viewer.
        """
        #Open viewer instance
        global lavavu
        if lavavu and uw.rank() == 0:
            #Generate db if doesn't exist
            if not self.db._db.path:
                self._generate_DB()
            v = self.db.lvrun()
            v.window()
            return v

    def open_viewer(self, args=[], background=True):
        """ Open the external viewer.
        """
        fname = self.db.filename
        if not fname:
            fname = os.path.join(tmpdir,"gluciferDB"+self.db._id+".gldb")
            self.save_database(fname)
        #Already open?
        if self._viewerProc and self._viewerProc.poll() == None:
            return

        global lavavu
        if lavavu and uw.rank() == 0:
            #Open viewer with local web server for interactive/iterative use
            if background:
                self._viewerProc = subprocess.Popen([self.db._lvbin, "-" + str(self.db.step), "-p9999", "-q90", fname] + args,
                                                    stdout=PIPE, stdin=PIPE, stderr=STDOUT)
                from IPython.display import HTML
                return HTML('''<a href='#' onclick='window.open("http://" + location.hostname + ":9999");'>Open Viewer Interface</a>''')
            else:
                self.db.lvrun(db=fname, port=9999)

    def close_viewer(self):
        """ Close the viewer.
        """
        #poll() returns None if the process is alive
        if self._viewerProc and self._viewerProc.poll() == None:
           self.send_command("quit")
           self._viewerProc.kill()
        self._viewerProc = None

    def send_command(self, cmd, retry=True):
        """ 
        Run command on an open viewer instance.
        
        Parameters
        ----------
        cmd: str
            Command to send to open viewer.
        """
        global lavavu
        if lavavu and uw.rank() == 0:
            self.open_viewer()
            url = "http://localhost:9999/command=" + urllib2.quote(cmd)
            try:
                #print url
                response = urllib2.urlopen(url).read()
                #print response
            except:
                print "Send command '" + cmd + "' failed, no response"
                if retry:
                    #Wait a few seconds so server has time to start then try again
                    print "... retrying in 1s ..."
                    time.sleep(1)
                    self.send_command(cmd, False)
                else:
                    print "... failed, skipping ..."
                    pass

    def clear(self):
        # DEPRECATE
        raise RuntimeError("This method is now deprecated.\n" \
                           "To obtain an empty figure just create a new one")

    def __add__(self,drawing_object):
        # DEPRECATE
        raise RuntimeError("This method is now deprecated.\n" \
                           "To add drawing objects to figures, use the append() method:\n" \
                           "    someFigure.append(someDrawingObject)")
    
    def append(self,drawingObject):
        """
        Add a drawing object to the figure. 
        
        Parameters
        ----------
        drawingObject: glucifer.objects.Drawing
            The drawing object to add to the figure
                
        
        """
        if not isinstance(drawingObject, objects.Drawing):
            raise TypeError("Object your are trying to add to figure does not appear to be of type 'Drawing'.")

        self._drawingObjects.append( drawingObject )

    @property
    def step(self):
        """    
        step (int): current timestep
        """
        return self.db.step

    @step.setter
    def step(self, value):
        #Sets new step on db
        self.db.step = value

class Viewer(dict):
    """  
    The Viewer class provides an interface to load stored figures and revisualise them
    
    In addition to parameter specification below, see property docstrings for
    further information.

    Parameters
    ----------
    filename: str
        Filename of database used to previously store the visualisation figures
            
    Example
    -------
        
    Create a reader using an existing database:
    
    >>> import glucifer
    >>> saved = glucifer.Viewer('vis.gldb')

    Iterate over the figures, print their names and plot them
    
    >>> for fig in saved:
    >>>     print(fig.name)

    Get first figure and display
    
    >>> fig = saved.next()
    >>> fig.show()

    Get a figure by name and display
    (A chosen name can be provided when creating the figures to make this easier)
    
    >>> fig = saved["myfig"]
    >>> fig.show()

    Display all figures at each timestep
    
    >>> for step in saved.steps:
    >>>    saved.step = step
    >>>    for name in saved:
    >>>        fig = saved[name]
    >>>        fig.quality = 3
    >>>        fig["title"] = "Timestep ##"
    >>>        fig.show()

    """

    _index = 0

    def __init__(self, filename, *args, **kwargs):
        if not isinstance(filename,str):
            raise TypeError("'filename' object passed in must be of python type 'str'")

        self._db = Store(filename, view=True)
        self.steps = [-1]

        super(Viewer, self).__init__(*args, **kwargs)

        global lavavu
        if not lavavu:
            print("LavaVu build is required to use Viewer")
            return

        #Load existing figures and save names
        states = self._db._read_state()
        if not states:
            return #No data
        for state in states:
            figname = str(state["figure"])
            fig = Figure(self._db, name=figname, **state["properties"])
            self[figname] = fig
            #Append objects, just create generic Drawing type to hold properties
            for obj in state["objects"]:
                if obj["visible"]:
                    fig.append(objects.Drawing(**obj))

        #Timestep info
        self.steps = self._db.timesteps

    def next(self):
        #Return next available figure and increment index
        if self._index >= len(self):
            self._index = 0
        key = list(self)[self._index]
        self._index += 1
        return self[key]

    @property
    def step(self):
        """    
        step (int): current timestep
        """
        return self._db.step

    @step.setter
    def step(self, value):
        #Sets new step on db
        self._db.step = value


