import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import cv2 as cv
import numpy as np

import multiprocessing

from PIL import Image, ImageTk
from ctypes import windll

import tqdm
import configparser as cfgparse

import winsound, time

windll.shcore.SetProcessDpiAwareness(True) ## no grainy interfaces

## why use parameters and returns in some complex structure when I could just bypass all that entirely
global LOADED_FILE_PATH
LOADED_FILE_PATH = ""

global PROCESS_MASK
PROCESS_MASK = False

global DO_FILTER
DO_FILTER = False

global PROCESS_METHOD ## this will be set later ^o^ teehee

global LOAD_NEW ## need this to be able to load more than one variable
LOAD_NEW = True

global VIEW_MODE
VIEW_MODE = "colour"


global FORCE_SIZE
FORCE_SIZE = (0.6, 0.6)
#FORCE_SIZE = (1, 1)

class VideoView:

    def __init__(self):

        global PROCESS_METHOD
        PROCESS_METHOD = self.process_entire_video

        self.feed = tk.Toplevel()

        self.video_frame = tk.LabelFrame(self.feed, text="Video")

        self.video_frame.grid(row=0, column=0, sticky="nsew")

        #self.cap = cv.VideoCapture(0)
        #ret, self.frame = self.cap.read()

        self.frame = np.ones((480, 640))
        ret = True

        self.PREVIEW_UPDATE_INTERVAL = 128
        self.preview_frame = None
        

        self.do_denoise_image = False
        self.denoise_h = 15

        if ret:
            self.video_canvas = tk.Canvas(self.video_frame, width=self.frame.shape[1], height=self.frame.shape[0])
            self.video_canvas.grid(row=0, column=0, sticky="nsew")

        self.mask = np.array([
            [0, 180], #h
            [0, 255], #s
            [0, 255]  #v
        ])

        self.update_preview()

        self.feed.mainloop()
        #self.cap.release()
    
    def read_next_frame(self):

        ret, frame = self.cap.read()

        ## cap gives bgr instead of rgb so flip that axis to get rgb
        self.frame = np.flip(frame, axis=2) ## equivalent of cvtColor with bgr2rgb

        
    def process_frame(self, frame, mask):
        
        ## frame is currently in rgb space, need it in hsv space
        processed_frame = cv.cvtColor(frame, cv.COLOR_RGB2HSV)

        min_h = mask[0][0]
        max_h = mask[0][1]
        min_s = mask[1][0]
        max_s = mask[1][1]
        min_v = mask[2][0]
        max_v = mask[2][1]


        if min_h < max_h:
            lower_hsv = np.array([min_h, min_s, min_v])
            upper_hsv = np.array([max_h, max_s, max_v])

            hsv_mask = cv.inRange(processed_frame, lower_hsv, upper_hsv)
            white_hsv = np.array([0, 0, 256])

            processed_frame = cv.bitwise_and(white_hsv, processed_frame, mask=hsv_mask)
            
        else:
            lower_hsv = np.array([0, min_s, min_v])
            upper_hsv = np.array([max_h, max_s, max_v])

            hsv_mask_pt1 = cv.inRange(processed_frame, lower_hsv, upper_hsv)

            lower_hsv = np.array([min_h, min_s, min_v])
            upper_hsv = np.array([180, max_s, max_v])

            hsv_mask_pt2 = cv.inRange(processed_frame, lower_hsv, upper_hsv)

            combined_mask = np.bitwise_or(hsv_mask_pt1, hsv_mask_pt2)
            white_hsv = np.array([0, 0, 256])

            processed_frame = cv.bitwise_and(white_hsv, processed_frame, mask=combined_mask)


        #processed_frame = cv.bitwise_and(white_hsv, processed_frame, mask=mask_hsv)

        ## gonna have to remember to set DO_FILTER to whatever is in the Denoise? checkbox when the signal to start processing frames goes
        global DO_FILTER

        if DO_FILTER == True:
            #processed_frame = cv.fastNlMeansDenoising(processed_frame, processed_frame, self.denoise_h)
            processed_frame = cv.medianBlur(processed_frame, self.denoise_h)
        
        ## make all pixels below vibrance of 2 white
        processed_frame = cv.cvtColor(processed_frame, cv.COLOR_HSV2RGB)
        processed_frame = cv.cvtColor(processed_frame, cv.COLOR_RGB2GRAY)

        _ret, processed_frame = cv.threshold(processed_frame, 0, 255, 0)

        processed_frame = cv.cvtColor(processed_frame, cv.COLOR_GRAY2RGB)

        self.processed_frame = processed_frame

        return processed_frame
    
    
    def find_tracker_position(self, masked_frame):

        masked_frame = cv.cvtColor(masked_frame, cv.COLOR_RGB2GRAY)
        
        y, x = np.where(masked_frame > 1) ## x, y are lists of indices of pixels where there is a non-black pixel

        tracker_x = np.average(x)
        tracker_y = np.average(y)
        
        ## used to filter out NaN - if pixel position is not positive it's set to -1, NaN is neither positive nor negative so this does work
        if not tracker_x > 0:
            tracker_x = -1
        if not tracker_y > 0:
            tracker_y = -1

        tracker_position = np.array([tracker_x, tracker_y])

        return tracker_position
    

    def draw_preview(self, frame):

        global FORCE_SIZE
        img_arr = Image.fromarray(frame)
        frame_size = (int(img_arr.width * FORCE_SIZE[0]), int(img_arr.height * FORCE_SIZE[1]))
        img_arr = img_arr.resize(frame_size)
        self.__frame_from_array__ = ImageTk.PhotoImage(image=img_arr)
        
        frame_coords = (int(frame_size[0] / 2), int(frame_size[1] / 2))
        self.__keep_image__ = self.video_canvas.create_image(frame_coords[0], frame_coords[1], image=self.__frame_from_array__)


    def update_preview(self):

        ## so check whats in the loaded file path var
        global LOADED_FILE_PATH
        global LOAD_NEW
        if LOAD_NEW == True: #if type(self.preview_frame) != type(np.ndarray(1)): ## if it's an array it must be loaded

            if LOADED_FILE_PATH != "":
                ## load file if the path exists, then use first frame as preview

                self.cap = cv.VideoCapture(LOADED_FILE_PATH.name)
                ret, preview = self.cap.read()


                print("read", LOADED_FILE_PATH)

                if ret:
                    ## let's set the window preview size to match video
                    self.video_canvas.config(width=preview.shape[1], height=preview.shape[0])

                    ## make the colour space alright ~THIS IS WHERE TO LOOK IF THE VIDEO IS LOOKING WRONG
                    self.preview_frame = self.master_frame = cv.cvtColor(preview, cv.COLOR_BGR2RGB) ## master frame to avoid overwriting the preview source
                    
                    global PROCESS_MASK
                    PROCESS_MASK = False

                else:
                    messagebox.showerror("Load Error", "Error loading file at " + str(LOADED_FILE_PATH))
                    LOADED_FILE_PATH = ""
                
                LOAD_NEW = False
            
            else:
                ## draw placeholder graphic
                NotImplemented
                ## this is my new favourite keyword
                ## like no,, it's just not done now
        
        else: ## draw preview frame, processed according to mask

            ## now we only want to process the frame if we want to process it
            #global PROCESS_MASK

            if PROCESS_MASK:
                self.mask = PROCESS_MASK
                self.preview_frame = self.process_frame(self.master_frame, self.mask) ## not a problem as self.process_frame does array -> array

                ## draw preview before tracker position
                self.draw_preview(self.preview_frame)

                ## if we're processing then we're viewing a channel so let's also find the tracker position
                tracker_position = self.find_tracker_position(self.preview_frame)
                self.video_canvas.create_rectangle(
                    tracker_position[0] - 5,
                    tracker_position[1] - 5,
                    tracker_position[0] + 5,
                    tracker_position[1] + 5,
                    fill="#ff0000"
                )

                #print(tracker_position)

            else:
                self.preview_frame = self.master_frame ## don't show processing if the view raw colour frame is selected

                self.draw_preview(self.preview_frame)


        self.feed.after(self.PREVIEW_UPDATE_INTERVAL, self.update_preview)
    
    def process_entire_video(self, masks):

        ## first load entire video into memory
        ## you'll have to assume const frame rate (opencv does too)

        global LOADED_FILE_PATH
        if LOADED_FILE_PATH == "": ## something must be loaded here

            messagebox.showerror("Process Error", "Please load a video to process first!")
            return -1

        loaded_video_frames = None

        self.cap = cv.VideoCapture(LOADED_FILE_PATH.name)
        fps = self.cap.get(cv.CAP_PROP_FPS)

        tracking_results = [[], [], []]

        print("Process progress...")

        frame_count = int(self.cap.get(cv.CAP_PROP_FRAME_COUNT))

        prog_bar = tqdm.tqdm(total=frame_count)
        while self.cap.isOpened():
            ret, frame = self.cap.read()

            if ret:
                loaded_video_frames = frame

            else:
                frame_count = int(self.cap.get(cv.CAP_PROP_FRAME_COUNT))

                if frame_count == len(tracking_results[0]):
                    winsound.Beep(600, 200)
                    time.sleep(0.2)
                    winsound.Beep(500, 300)
                    time.sleep(0.3)
                    #winsound.Beep(600, 200)
                    messagebox.showinfo("File Read", str(frame_count) + " frame(s) loaded successfully")
                else:
                    messagebox.showwarning("End of Video", "Could not load next frame in video (expected " + str(frame_count) + ", got " + str(len(tracking_results[0]))+").")
                break
        


            self.loaded_frames = loaded_video_frames

             ## make a couple of threads to process in parallel ?

            cha_results = self.process_thread(frame, masks[0])
            chb_results = self.process_thread(frame, masks[1])
            chc_results = self.process_thread(frame, masks[2])

            tracking_results[0].append(cha_results)
            tracking_results[1].append(chb_results)
            tracking_results[2].append(chc_results)

            prog_bar.update()

        self.cap.release()
        prog_bar.close()

        messagebox.showinfo("Processing Results", "All threads complete with result shape of " + str(np.array(tracking_results).shape))
        #print(tracking_results[0])

        self.output_data(fps, tracking_results)
        
        
    def process_thread(self, frame, mask):#, progress_bar, frame_counter):


        #print("one ring [progress pars are not circular] to rule them all"

        #print("start of thread", ret_index)

        processed_frame = self.process_frame(frame, mask)
        tracker_position = self.find_tracker_position(processed_frame)

        return tracker_position

    def output_data(self, fps, results):
        
        row = []
        for i in range(len(results[1])):
            
            ## iterate through the results data to see if any are NaN and replace with -1
            ch_a = results[0][i]
            ch_b = results[1][i]
            ch_c = results[2][i]

            print(ch_a, ch_b, ch_c)


            row.append([i / fps, results[0][i][0], results[0][i][1], results[1][i][0], results[1][i][1], results[2][i][0], results[2][i][1]])

        out_filename = LOADED_FILE_PATH.name + "_out.txt"
        print(out_filename)
        np.savetxt(out_filename, np.array(row))
        
        
        
class MaskOptioniser:

    def __init__(self, root, view_var, channel="A"):
        

        self.channel = channel


        self.frame = tk.LabelFrame(root, text="Channel " + channel, width=500)

        h_frame = tk.LabelFrame(self.frame, text="Hue min/max")
        self.h_min_slider = tk.Scale(h_frame, from_=0, to=180, orient="horizontal", command=self.update_mask_values)
        self.h_max_slider = tk.Scale(h_frame, from_=0, to=180, orient="horizontal", command=self.update_mask_values)
        self.h_max_slider.set(180)

        self.h_min_slider.grid(row=0, column=1)
        self.h_max_slider.grid(row=1, column=1)

        h_frame.grid(row=0, column=0, padx=8, columnspan=2)



        s_frame = tk.LabelFrame(self.frame, text="Sat. min/max")
        self.s_min_slider = tk.Scale(s_frame, from_=0, to=255, orient="horizontal", command=self.update_mask_values)
        self.s_max_slider = tk.Scale(s_frame, from_=0, to=255, orient="horizontal", command=self.update_mask_values)
        self.s_max_slider.set(255)

        self.s_min_slider.grid(row=0, column=1)
        self.s_max_slider.grid(row=1, column=1)

        s_frame.grid(row=1, column=0, pady=10, columnspan=2)



        v_frame = tk.LabelFrame(self.frame, text="Vib. min/max")
        self.v_min_slider = tk.Scale(v_frame, from_=0, to=255, orient="horizontal", command=self.update_mask_values)
        self.v_max_slider = tk.Scale(v_frame, from_=0, to=255, orient="horizontal", command=self.update_mask_values)
        self.v_max_slider.set(255)

        self.v_min_slider.grid(row=0, column=1)
        self.v_max_slider.grid(row=1, column=1)

        v_frame.grid(row=2, column=0, columnspan=2)

        self.view_raw = tk.Radiobutton(self.frame, text="Raw", variable=view_var, value=channel+"_raw", command=self.set_raw)
        self.view_raw.grid(row=3, column=0)

        self.view_filter = tk.Radiobutton(self.frame, text="Filtered", variable=view_var, value=channel+"_filtered", command=self.set_filtered)
        self.view_filter.grid(row=3, column=1)

        self.set_filtered()


    def grid(self, *args, **kwargs):
        self.frame.grid(*args, **kwargs)
    
    def get_mask_values(self):

        h_mask = [self.h_min_slider.get(), self.h_max_slider.get()]
        s_mask = [self.s_min_slider.get(), self.s_max_slider.get()]
        v_mask = [self.v_min_slider.get(), self.v_max_slider.get()]

        return h_mask, s_mask, v_mask
    
    def set_mask_values(self, mask):

        print(mask)

        self.h_min_slider.set(mask[0][0])
        self.h_max_slider.set(mask[0][1])

        self.s_min_slider.set(mask[1][0])
        self.s_max_slider.set(mask[1][1])

        self.v_min_slider.set(mask[2][0])
        self.v_max_slider.set(mask[2][1])

        self.update_mask_values()
    
    def set_raw(self):

        global DO_FILTER
        DO_FILTER = False

        global PROCESS_MASK
        PROCESS_MASK = self.get_mask_values()
    
    def set_filtered(self):
        self.set_raw()

        global DO_FILTER
        DO_FILTER = True
    
    ## this is called every time the slider value is changed such that the preview updates real-time (no more radio button pressing !! :) )
    def update_mask_values(self, *args, **kwargs):

        global PROCESS_MASK
        PROCESS_MASK = self.get_mask_values()

        ## set the filtering to the correct value when the masking is updated

        global DO_FILTER
        



class CtrlPanel:

    def __init__(self):

        self.control_root = tk.Tk()
        
        ## loading ##
        load_frame = tk.Frame(self.control_root)
        self.load_button = ttk.Button(load_frame, text="Open File", command=self.open_file)

        self.load_button.grid(row=0, column=0, columnspan=3)
        load_frame.grid(row=0, column=0, columnspan=3, pady=5)

        separator = ttk.Separator(self.control_root, orient="horizontal")
        separator.grid(row=1, column=0, columnspan=3, sticky="NSEW")


        ## masking ##
        self.view_mode = tk.StringVar()

        self.ch_a = MaskOptioniser(self.control_root, self.view_mode, channel="A")
        self.ch_b = MaskOptioniser(self.control_root, self.view_mode, channel="B")
        self.ch_c = MaskOptioniser(self.control_root, self.view_mode, channel="C")

        self.ch_a.grid(row=2, column=0)
        self.ch_b.grid(row=2, column=1)
        self.ch_c.grid(row=2, column=2)

        separator = ttk.Separator(self.control_root, orient="horizontal")
        separator.grid(row=3, column=0, columnspan=3, sticky="NSEW", pady=5)

        self.frame_view = tk.Radiobutton(self.control_root, text="View Colour Frame", variable=self.view_mode, value="RAW", command=self.set_view_raw)
        self.frame_view.grid(row=4, column=0, columnspan=3)

        self.frame_view.select()
        self.set_view_raw()

        separator = ttk.Separator(self.control_root, orient="horizontal")
        separator.grid(row=5, column=0, columnspan=3, sticky="NSEW", pady=5)

        ## denoising ##
        self.do_denoise = tk.BooleanVar()

        denoise_frame = tk.Frame(self.control_root)
        denoise_frame.grid(row=6, column=0, columnspan=3, sticky="NSEW")

        self.do_denoise_check = tk.Checkbutton(denoise_frame, variable=self.do_denoise, text="Denoise output?")
        self.do_denoise_check.grid(row=0, column=0, sticky="NSEW", columnspan=1)

        separator = ttk.Separator(self.control_root, orient="horizontal")
        separator.grid(row=7, column=0, columnspan=3, sticky="NSEW", pady=5)

        ## start ##
        self.begin_processing_btn = ttk.Button(self.control_root, text="Begin !", command=self.start_processing)

        self.begin_processing_btn.grid(row=8, column=0, columnspan=3, pady=3)
        
        ## load presets ##
        ctrl_menubar = tk.Menu(self.control_root)
        file_menu = tk.Menu(ctrl_menubar, tearoff=0)

        file_menu.add_command(label="Load Channel Preset ...", command=self.load_channel_presets)
        file_menu.add_command(label="Save Channel Preset ...", command=self.save_channel_presets)

        ctrl_menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(ctrl_menubar, tearoff=0)

        view_menu.add_cascade(label="Show Preview Window", command=VideoView)

        step_menu = tk.Menu(view_menu, tearoff=0)
        step_menu.add_command(label="Forwards")
        step_menu.add_command(label="Backwards")

        view_menu.add_cascade(label="Step...", menu=step_menu)

        ctrl_menubar.add_cascade(label="View", menu=view_menu)

        self.control_root.config(menu=ctrl_menubar)
    
    def open_file(self):
        global LOADED_FILE_PATH
        LOADED_FILE_PATH = filedialog.askopenfile(mode="r")

        global LOAD_NEW
        LOAD_NEW = True
    
    def set_view_raw(self):

        global DO_FILTER
        DO_FILTER = False

        global PROCESS_MASK
        PROCESS_MASK = False ## nuh uh to processing at this time
    
    def start_processing(self):
        global DO_FILTER
        DO_FILTER = self.do_denoise.get()

        masks = [self.ch_a.get_mask_values(), self.ch_b.get_mask_values(), self.ch_c.get_mask_values()]

        global PROCESS_METHOD
        PROCESS_METHOD(masks)
    
    def save_channel_presets(self):
        
        masks = [self.ch_a.get_mask_values(), self.ch_b.get_mask_values(), self.ch_c.get_mask_values()]
        
        config = cfgparse.ConfigParser()
        
        for channel, mask in enumerate(masks):
            config[["A", "B", "C"][channel]] = {"mask":mask}
        
        file_path = filedialog.asksaveasfile(defaultextension="*.ini", filetypes=[("Config", "*.ini")])
        print(file_path)
        with open(file_path.name, "w") as file:
            config.write(file)
    
    def load_channel_presets(self):

        file_path = filedialog.askopenfile(mode="r", defaultextension="*.ini", filetypes=[("Config", "*.ini")])
        #print(file_path)

        config = cfgparse.ConfigParser()
        file = config.read(file_path.name)

        a_mask = config.get("A", "mask")
        b_mask = config.get("B", "mask")
        c_mask = config.get("C", "mask")

        def load_mask(mask_str):
            mask_str = mask_str.replace("]", "").replace(")", "").split("[")
            mask_str = [mask_str[1], mask_str[2], mask_str[3]]
            

            mask = (
                mask_str[0].split(", ")[:2],
                mask_str[1].split(", ")[:2],
                mask_str[2].split(", ")[:2],
            )

            print(mask)
            mask = (
                [int(mask[0][0]), int(mask[0][1])],
                [int(mask[1][0]), int(mask[1][1])],
                [int(mask[2][0]), int(mask[2][1])],
            )


            return mask

        a_mask = load_mask(a_mask)
        b_mask = load_mask(b_mask)
        c_mask = load_mask(c_mask)
            
        self.ch_a.set_mask_values(a_mask)
        self.ch_b.set_mask_values(b_mask)
        self.ch_c.set_mask_values(c_mask) 
        



#print("START PROFILING")
## profiling::
import cProfile

print(cv.useOptimized()* "openCV running optimally" + (cv.useOptimized()==False)*"openCV not running optimally")

ctrl = CtrlPanel()
vv = VideoView()
