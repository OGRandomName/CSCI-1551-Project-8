# dronepatterns.py
import math
import random
from panda3d.core import Vec3
from classes import DroneDefender

# ---------------------------------------------------------
# Helper: generate evenly spaced angles
# ---------------------------------------------------------
def evenly_spaced_angles(n):
    step = (2 * math.pi) / n
    return [i * step for i in range(n)]

# ---------------------------------------------------------
# Circle X Pattern (YZ plane)
# ---------------------------------------------------------
def circleX_pattern(game, center_pos, num_drones=12, radius=20):
    drones = []
    cx, cy, cz = center_pos
    angles = evenly_spaced_angles(num_drones)

    for i, angle in enumerate(angles):
        x = cx
        y = cy + radius * math.cos(angle)
        z = cz + radius * math.sin(angle)

        drone = DroneDefender(
            name=f"DroneX_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x, y, z),
            orbit_radius=radius
        )
        drone.orbit_mode = "circleX"
        drone.orbit_center = center_pos
        drone.orbit_angle = angle
        drone.orbit_speed = 0.3

        drones.append(drone)

    return drones

# ---------------------------------------------------------
# Circle Y Pattern (XZ plane)
# ---------------------------------------------------------
def circleY_pattern(game, center_pos, num_drones=12, radius=20):
    drones = []
    cx, cy, cz = center_pos
    angles = evenly_spaced_angles(num_drones)

    for i, angle in enumerate(angles):
        x = cx + radius * math.cos(angle)
        y = cy
        z = cz + radius * math.sin(angle)

        drone = DroneDefender(
            name=f"DroneY_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x, y, z),
            orbit_radius=radius
        )
        drone.orbit_mode = "circleY"
        drone.orbit_center = center_pos
        drone.orbit_angle = angle
        drone.orbit_speed = 0.3

        drones.append(drone)

    return drones

# ---------------------------------------------------------
# Circle Z Pattern (XY plane)
# ---------------------------------------------------------
def circleZ_pattern(game, center_pos, num_drones=12, radius=20):
    drones = []
    cx, cy, cz = center_pos
    angles = evenly_spaced_angles(num_drones)

    for i, angle in enumerate(angles):
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        z = cz

        drone = DroneDefender(
            name=f"DroneZ_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x, y, z),
            orbit_radius=radius
        )

        drone.orbit_mode = "circleZ"
        drone.orbit_center = center_pos
        drone.orbit_angle = angle
        drone.orbit_speed = 0.3

        drones.append(drone)

    return drones

# ---------------------------------------------------------
# Cloud Pattern (random points on a sphere)
# ---------------------------------------------------------
def cloud_pattern(game, center_pos, num_drones=20, radius=40):
    drones = []
    cx, cy, cz = center_pos

    for i in range(num_drones):
        theta = random.random() * 2 * math.pi
        phi = math.acos(2 * random.random() - 1)

        x = cx + radius * math.sin(phi) * math.cos(theta)
        y = cy + radius * math.sin(phi) * math.sin(theta)
        z = cz + radius * math.cos(phi)

        drone = DroneDefender(
            name=f"CloudDrone_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x, y, z),
            orbit_radius=radius
        )

        drone.orbit_mode = "cloud"
        drone.orbit_center = center_pos
        drone.orbit_angle = theta
        drone.orbit_speed = 0.2

        drones.append(drone)

    return drones

# ---------------------------------------------------------
# Baseball Seams Pattern (both seams orbit)
# ---------------------------------------------------------
def baseball_seams_pattern(game, center_pos, num_drones=20, radius=40):
    drones = []
    cx, cy, cz = center_pos
    angles = evenly_spaced_angles(num_drones)

    for i, t in enumerate(angles):
        # Seam 1
        x1 = cx + radius * math.cos(t)
        y1 = cy + radius * math.sin(t)
        z1 = cz + radius * 0.3 * math.sin(2 * t)

        drone1 = DroneDefender(
            name=f"Seam1_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x1, y1, z1),
            orbit_radius=radius
        )

        drone1.orbit_mode = "seams"
        drone1.orbit_center = center_pos
        drone1.orbit_angle = t
        drone1.orbit_speed = 0.25
        drones.append(drone1)

        # Seam 2 (opposite)
        t2 = t + math.pi
        x2 = cx + radius * math.cos(t2)
        y2 = cy + radius * math.sin(t2)
        z2 = cz + radius * 0.3 * math.sin(2 * t2)

        drone2 = DroneDefender(
            name=f"Seam2_{i}",
            model_path="Assets/DroneDefender/DroneDefender.egg",
            scale=8.0,
            position=(x2, y2, z2),
            orbit_radius=radius
        )

        drone2.orbit_mode = "seams"
        drone2.orbit_center = center_pos
        drone2.orbit_angle = t2
        drone2.orbit_speed = 0.25
        drones.append(drone2)

    return drones


# =========================================================
# NEW LOGIC ADDED BELOW (EASING + ORBIT ENGINE)
# =========================================================

# ---------------------------------------------------------
# MEDIUM BACK EASING (B4-B)
# ---------------------------------------------------------
def ease_in_out_back(t):
    if t <= 0:
        return 0
    if t >= 1:
        return 1

    overshoot = 1.70158 * 1.3  # medium overshoot

    if t < 0.5:
        t2 = t * 2
        return 0.5 * (t2 * t2 * ((overshoot + 1) * t2 - overshoot))
    else:
        t2 = (t * 2) - 2
        return 0.5 * (t2 * t2 * ((overshoot + 1) * t2 + overshoot) + 2)


# ---------------------------------------------------------
# ANGLE REALIGNMENT PER PATTERN
# ---------------------------------------------------------
def compute_orbit_angle(drone, fx, fy, fz):
    cx, cy, cz = drone.orbit_center

    if drone.orbit_mode == "circleZ":
        return math.atan2(fy - cy, fx - cx)

    elif drone.orbit_mode == "circleX":
        return math.atan2(fz - cz, fy - cy)

    elif drone.orbit_mode == "circleY":
        return math.atan2(fz - cz, fx - cx)

    elif drone.orbit_mode == "cloud":
        dx = fx - cx
        dy = fy - cy
        return math.atan2(dy, dx)

    elif drone.orbit_mode == "seams":
        return math.atan2(fy - cy, fx - cx)

    return math.atan2(fy - cy, fx - cx)


# ---------------------------------------------------------
# ORBIT MATH (per pattern)
# ---------------------------------------------------------
def update_orbit(drone, dt):
    drone.orbit_angle += drone.orbit_speed * dt

    cx, cy, cz = drone.orbit_center
    r = drone.orbit_radius
    a = drone.orbit_angle

    if drone.orbit_mode == "circleX":
        x = cx
        y = cy + r * math.cos(a)
        z = cz + r * math.sin(a)

    elif drone.orbit_mode == "circleY":
        x = cx + r * math.cos(a)
        y = cy
        z = cz + r * math.sin(a)

    elif drone.orbit_mode == "circleZ":
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        z = cz

    elif drone.orbit_mode == "cloud":
        x = cx + r * math.cos(a) * math.cos(a)
        y = cy + r * math.sin(a) * math.cos(a)
        z = cz + r * math.sin(a)

    elif drone.orbit_mode == "seams":
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        z = cz + r * 0.3 * math.sin(2 * a)

    else:
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        z = cz

    return Vec3(x, y, z)


# ---------------------------------------------------------
# TRANSITION LOGIC
# ---------------------------------------------------------
def update_transition(drone, dt, orbit_target):
    if drone.transition_active and drone.target_pos is None:
        drone.target_pos = orbit_target

    if drone.transition_active:
        drone.transition_time += dt
        t = drone.transition_time / drone.transition_duration

        if t >= 1.0:
            final_pos = drone.target_pos
            drone.transition_active = False
            drone.target_pos = None
            drone.start_pos = None

            fx, fy, fz = final_pos
            drone.orbit_angle = compute_orbit_angle(drone, fx, fy, fz)

            return final_pos

        smooth_t = ease_in_out_back(t)
        return drone.start_pos * (1 - smooth_t) + drone.target_pos * smooth_t

    return orbit_target
