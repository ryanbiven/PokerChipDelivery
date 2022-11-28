class TrackingParams(object):
    color_lower = (100, 75, 75)
    color_upper = (135, 255, 255)
    allowed_distance = 50
    move_speed = 20
    turn_speed = 20
    landing_radius = 250
    track_spin = 45
    track_up = 10

    # tracking a color
    # green_lower = (30, 50, 50)
    # green_upper = (80, 255, 255)
    # orange_lower = (5, 50, 50)
    # orange_upper = (30, 255, 255)
    # red_lower = (0, 50, 50)
    # red_upper = (20, 255, 255)
    # blue_lower = (110, 50, 50)
    # upper_blue = (130, 255, 255)

    # define the lower and upper boundaries of the "green"
    # ball in the HSV color space. NB the hue range in
    # opencv is 180, normally it is 360
