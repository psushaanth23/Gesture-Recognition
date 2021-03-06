#!/usr/bin/python

import cv2
import numpy as np
import math
from Gestures import *
from unix import PyMouse

hsv_thresh_lower=150
gaussian_ksize=11
gaussian_sigma=0
morph_elem_size=13
median_ksize=3
capture_box_count=9
capture_box_dim=20
capture_box_sep_x=8
capture_box_sep_y=18    
capture_pos_x=500
capture_pos_y=150
cap_region_x_begin=0.5
cap_region_y_end=0.8
finger_thresh_l=2.0
finger_thresh_u=3.8
radius_thresh=0.04
first_iteration=True
finger_ct_history=[0,0]
global gesture_found


def capture_hand_histogram(frame_in,box_x,box_y):
    hsv = cv2.cvtColor(frame_in, cv2.COLOR_BGR2HSV)
    ROI = np.zeros([capture_box_dim*capture_box_count,capture_box_dim,3], dtype=hsv.dtype)
    for i in xrange(capture_box_count):
        ROI[i*capture_box_dim:i*capture_box_dim+capture_box_dim,0:capture_box_dim] = hsv[box_y[i]:box_y[i]+capture_box_dim,box_x[i]:box_x[i]+capture_box_dim]
    hand_hist = cv2.calcHist([ROI],[0, 1], None, [180, 256], [0, 180, 0, 256])
    cv2.normalize(hand_hist,hand_hist, 0, 255, cv2.NORM_MINMAX)

    cv2.imshow('Normalized Histogram',hand_hist)
    return hand_hist

def hand_threshold(frame_in,hand_hist):
    frame_in=cv2.medianBlur(frame_in,3)
    hsv=cv2.cvtColor(frame_in,cv2.COLOR_BGR2HSV)
    cv2.imshow('hsv',hsv)
    #hsv[0:int(cap_region_y_end*hsv.shape[0]),0:int(cap_region_x_begin*hsv.shape[1])]=0 # Right half screen only
    #hsv[int(cap_region_y_end*hsv.shape[0]):hsv.shape[0],0:hsv.shape[1]]=0
    back_projection = cv2.calcBackProject([hsv], [0,1],hand_hist, [00,180,0,256], 1)
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_elem_size,morph_elem_size))
    cv2.filter2D(back_projection, -1, disc, back_projection)
    back_projection=cv2.GaussianBlur(back_projection,(gaussian_ksize,gaussian_ksize), gaussian_sigma)
    back_projection=cv2.medianBlur(back_projection,median_ksize)
    ret, thresh = cv2.threshold(back_projection, hsv_thresh_lower, 255, 0)
    
    return thresh

def max_contour_find(contours):
    max_area=0
    largest_contour=-1
    for i in range(len(contours)):
        cont=contours[i]
        area=cv2.contourArea(cont)
        if(area>max_area):
            max_area=area
            largest_contour=i
    if(largest_contour==-1):
        return False,0
    else:
        h_contour=contours[largest_contour]
        return True,h_contour

def mark_fingers(frame_in,hull,pt,radius):
    global first_iteration
    global finger_ct_history
    finger=[(hull[0][0][0],hull[0][0][1])]
    j=0

    cx = pt[0]
    cy = pt[1]
    
    for i in range(len(hull)):
        dist = np.sqrt((hull[-i][0][0] - hull[-i+1][0][0])**2 + (hull[-i][0][1] - hull[-i+1][0][1])**2)
        if (dist>18):
            if(j==0):
                finger=[(hull[-i][0][0],hull[-i][0][1])]
            else:
                finger.append((hull[-i][0][0],hull[-i][0][1]))
            j=j+1
    
    temp_len=len(finger)
    i=0
    while(i<temp_len):
        dist = np.sqrt( (finger[i][0]- cx)**2 + (finger[i][1] - cy)**2)
        if(dist<finger_thresh_l*radius or dist>finger_thresh_u*radius or finger[i][1]>cy+radius):
            finger.remove((finger[i][0],finger[i][1]))
            temp_len=temp_len-1
        else:
            i=i+1        
    
    temp_len=len(finger)
    if(temp_len>5):
        for i in range(1,temp_len+1-5):
            finger.remove((finger[temp_len-i][0],finger[temp_len-i][1]))
    
    palm=[(cx,cy),radius]

    if(first_iteration):
        finger_ct_history[0]=finger_ct_history[1]=len(finger)
        first_iteration=False
    else:
        finger_ct_history[0]=0.34*(finger_ct_history[0]+finger_ct_history[1]+len(finger))

    global finger_count
    if((finger_ct_history[0]-int(finger_ct_history[0]))>0.8):
        finger_count=int(finger_ct_history[0])+1
    else:
        finger_count=int(finger_ct_history[0])

    finger_ct_history[1]=len(finger)

    count_text="FINGERS:"+str(finger_count)
    cv2.putText(frame_in,count_text,(int(0.62*frame_in.shape[1]),int(0.88*frame_in.shape[0])),cv2.FONT_HERSHEY_DUPLEX,1,(0,255,255),1,8)

    for k in range(len(finger)):
        cv2.circle(frame_in,finger[k],10,255,2)
        cv2.line(frame_in,finger[k],(cx,cy),255,2)
    return frame_in,finger,palm

def mark_hand_center(frame_in,cont):    
    max_d=0
    pt=(0,0)
    x,y,w,h = cv2.boundingRect(cont)
    for ind_y in xrange(int(y+0.3*h),int(y+0.8*h)): #around 0.25 to 0.6 region of height (Faster calculation with ok results)
        for ind_x in xrange(int(x+0.3*w),int(x+0.6*w)): #around 0.3 to 0.6 region of width (Faster calculation with ok results)
            dist= cv2.pointPolygonTest(cont,(ind_x,ind_y),True)
            if(dist>max_d):
                max_d=dist
                pt=(ind_x,ind_y)
    if(max_d>radius_thresh*frame_in.shape[1]):
        thresh_score=True
        cv2.circle(frame_in,pt,int(max_d),(255,0,0),2)
    else:
        thresh_score=False
    return frame_in,pt,max_d,thresh_score

# 6. Find and display gesture

def find_gesture(frame_in,finger,palm):
    frame_gesture.set_palm(palm[0],palm[1])
    frame_gesture.set_finger_pos(finger)
    frame_gesture.calc_angles()
    gesture_found = DecideGesture(frame_gesture,GestureDictionary)
    gesture_text="Recognition:"+str(gesture_found)
    
    if(finger_count == 0 or gesture_found == 'V' or gesture_found == 'L'):
        moveMouse()

    cv2.putText(frame_in,gesture_text,(int(0.56*frame_in.shape[1]),int(0.97*frame_in.shape[0])),cv2.FONT_HERSHEY_DUPLEX,1,(0,255,255),1,8)
    return frame_in,gesture_found

def remove_bg(frame):
    fg_mask=bg_model.apply(frame)
    kernel = np.ones((3,3),np.uint8)
    fg_mask=cv2.erode(fg_mask,kernel,iterations = 5)
    fg_mask=cv2.dilate(fg_mask,kernel,iterations = 5)
    

    frame=cv2.bitwise_and(frame,frame,mask=fg_mask)
    #cv2.imshow('back1',fg_mask)
    #cv2.imshow('frame3',frame)
    return frame

def moveMouse():
    X,Y=mouse.position()
    scalex = width/640
    scaley = height/480
    if(finger_count == 0):
        mouse.move(hand_center[0],hand_center[1])
    elif(gesture_found == 'V'):
        mouse.click(hand_center[0],hand_center[1],1)
    elif(gesture_found == 'L'):
        mouse.click(hand_center[0],hand_center[1],2)

    print hand_center


camera = cv2.VideoCapture(0)
capture_done=0
bg_captured=0
GestureDictionary=DefineGestures()
frame_gesture=Gesture("frame_gesture")
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
mouse = PyMouse()
width,height= mouse.screen_size()

while(1):
    ret, frame = camera.read()
    frame=cv2.bilateralFilter(frame,5,50,100)
    # Operations on the frame
    frame=cv2.flip(frame,1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for (x,y,w,h) in faces:
        cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = frame[y:y+h, x:x+w]


    #cv2.rectangle(frame,(int(cap_region_x_begin*frame.shape[1]),0),(frame.shape[1],int(cap_region_y_end*frame.shape[0])),(255,0,0),1)
    frame_original=np.copy(frame)
    if(bg_captured):
        fg_frame=remove_bg(frame)
    
    #goes only when bg_capture and capture_hand are not done    
    if (not (capture_done and bg_captured)):
        if(not bg_captured):
            cv2.putText(frame,"Remove hand from the frame and press 'b' to capture background",(int(0.05*frame.shape[1]),int(0.97*frame.shape[0])),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1,8)
        else:
            cv2.putText(frame,"Place hand inside boxes and press 'c' to capture hand histogram",(int(0.08*frame.shape[1]),int(0.97*frame.shape[0])),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1,8)
        first_iteration=True
        finger_ct_history=[0,0]
        box_pos_x=np.array([capture_pos_x,capture_pos_x+capture_box_dim+capture_box_sep_x,capture_pos_x+2*capture_box_dim+2*capture_box_sep_x,capture_pos_x,capture_pos_x+capture_box_dim+capture_box_sep_x,capture_pos_x+2*capture_box_dim+2*capture_box_sep_x,capture_pos_x,capture_pos_x+capture_box_dim+capture_box_sep_x,capture_pos_x+2*capture_box_dim+2*capture_box_sep_x],dtype=int)
        box_pos_y=np.array([capture_pos_y,capture_pos_y,capture_pos_y,capture_pos_y+capture_box_dim+capture_box_sep_y,capture_pos_y+capture_box_dim+capture_box_sep_y,capture_pos_y+capture_box_dim+capture_box_sep_y,capture_pos_y+2*capture_box_dim+2*capture_box_sep_y,capture_pos_y+2*capture_box_dim+2*capture_box_sep_y,capture_pos_y+2*capture_box_dim+2*capture_box_sep_y],dtype=int)
        for i in range(capture_box_count):
            cv2.rectangle(frame,(box_pos_x[i],box_pos_y[i]),(box_pos_x[i]+capture_box_dim,box_pos_y[i]+capture_box_dim),(255,0,0),1)
    else:
        frame=hand_threshold(fg_frame,hand_histogram)
        frame[y-20:y+h+20,x-20:x+w+20]=0
        cv2.imshow('thresholded hand histogram',frame)
        contour_frame=np.copy(frame)
        contours,hierarchy=cv2.findContours(contour_frame,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        found,hand_contour=max_contour_find(contours)
        if(found):
            hand_convex_hull=cv2.convexHull(hand_contour)
            frame,hand_center,hand_radius,hand_size_score=mark_hand_center(frame_original,hand_contour)
            if(hand_size_score):
                frame,finger,palm=mark_fingers(frame,hand_convex_hull,hand_center,hand_radius)
                frame,gesture_found=find_gesture(frame,finger,palm)
        else:
            frame=frame_original

    cv2.imshow('Hand Gesture Recognition v1.0',frame)
    interrupt=cv2.waitKey(10)
    
    if  interrupt & 0xFF == ord('q'):
        break
    
    elif interrupt & 0xFF == ord('c'):
        if(bg_captured):
            capture_done=1
            hand_histogram=capture_hand_histogram(frame_original,box_pos_x,box_pos_y)
    
    elif interrupt & 0xFF == ord('b'):
        bg_model = cv2.BackgroundSubtractorMOG2(0,10)
        bg_captured=1
    
    elif interrupt & 0xFF == ord('r'):
        capture_done=0
        bg_captured=0
        
camera.release()
cv2.destroyAllWindows()
