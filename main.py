from djitellopy import Tello

if __name__ == '__main__':
    tello = Tello()

    tello.connect()
    tello.takeoff()

    tello.move_left(100)
    tello.rotate_counter_clockwise(90)
    tello.move_forward(100)

    tello.land()
