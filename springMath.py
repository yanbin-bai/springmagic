import math
import pymel.core as pm
import pymel.core.datatypes as dt


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def distance(a, b):
    return (b - a).length()


def lerp_vec(a, b, t):
    return (a * (1 - t)) + (b * t)


def dist_to_plane(pt, n, d):
    return n.dot(pt) - (d / n.dot(n))


def dist_to_line(a, b, p):
    ap = p - a
    ab = b - a
    result = a + ((ap.dot(ab) / ab.dot(ab)) * ab)
    return distance(result, p)


def is_same_side_of_plane(pt, test_pt, n, d):
    d1 = math.copysign(1, dist_to_plane(pt, n, d))
    d2 = math.copysign(1, dist_to_plane(test_pt, n, d))

    # print(pt, test_pt, d1, d2)
    return d1 * d2 == 1.0


def proj_pt_to_plane(pt, n, d):
    t = n.dot(pt) - d
    return (pt - (n * t))


def pt_in_sphere(pt, c, r):
    return (pt - c).length() <= r


def pt_in_cylinder(pt, p, q, r):
    n = (q - p).normal()
    d = n.dot(p)

    if not is_same_side_of_plane(pt, (p + q) / 2.0, n, d):
        return False

    n = (q - p).normal()
    d = n.dot(q)

    if not is_same_side_of_plane(pt, (p + q) / 2.0, n, d):
        return False

    proj_pt = proj_pt_to_plane(pt, n, d)
    # logging("proj_pt", proj_pt)
    # logging("q", q)
    # logging("distance(proj_pt, q)", distance(proj_pt, q))

    return distance(proj_pt, q) <= r


def segment_sphere_isect(sa, sb, c, r):
    NotFound = (False, None)

    p = sa
    d = (sb - sa).normal()

    m = p - c
    b = m.dot(d)
    c = m.dot(m) - r * r

    if c > 0.0 and b > 0.0:
        return NotFound

    discr = b * b - c
    if discr < 0.0:
        return NotFound

    t = -b - math.sqrt(discr)
    if t < 0.0:
        return NotFound

    dist = distance(sa, sb)
    q = p + d * t
    return ((t >= 0 and t <= dist), q)


def segment_cylinder_isect(sa, sb, p, q, r):
    SM_EPSILON = 1e-6
    d = q - p
    m = sa - p
    n = sb - sa
    md = m.dot(d)
    nd = n.dot(d)
    dd = d.dot(d)

    NotFound = (False, None)
    if md < 0 and md + nd < 0:
        return NotFound

    if md > dd and md + nd > dd:
        return NotFound

    nn = n.dot(n)
    mn = m.dot(n)

    a = dd * nn - nd * nd
    k = m.dot(m) - r * r
    c = dd * k - md * md

    if abs(a) < SM_EPSILON:
        if c > 0:
            return NotFound
        if md < 0:
            t = -mn / nn
        elif md > dd:
            t = (nd - mn) / nn
        else:
            t = 0
        return (True, lerp_vec(sa, sb, t))

    b = dd * mn - nd * md
    discr = b * b - a * c
    if discr < 0:
        return NotFound

    t = (-b - math.sqrt(discr)) / a
    if t < 0.0 or t > 1.0:
        return NotFound
    if (md + t * nd < 0.0):
        if nd <= 0.0:
            return NotFound
        t = -md / nd
        return (k + 2 * t * (mn + t * nn) <= 0.0, lerp_vec(sa, sb, t))
    elif md + t * nd > dd:
        if nd >= 0.0:
            return NotFound
        t = (dd - md) / nd
        return (k + dd - 2 * md + t * (2 * (mn - nd) + t * nn) <= 0.0, lerp_vec(sa, sb, t))

    return (True, lerp_vec(sa, sb, t))


def pt_in_capsule(pt, p, q, r):
    return pt_in_cylinder(pt, p, q, r) or pt_in_sphere(pt, p, r) or pt_in_sphere(pt, q, r)


def segment_capsule_isect(sa, sb, p, q, r):
    # sa = dt.Vector()
    #    ray start point pos vector
    # sb = dt.Vector()
    #    ray end point pos vector
    # p = dt.Vector()
    #    capsle one sphere tip pos
    # q = dt.Vector()
    #    capsle another sphere tip pos
    # r = float
    #    radio of capsle sphere

    if pt_in_capsule(sa, p, q, r):
        if pt_in_capsule(sb, p, q, r):
            # both inside. extend sb to get intersection
            newb = sa + (sb - sa).normal() * 200.0
            sa, sb = newb, sa
        else:
            sb, sa = sa, sb

    # d = (sb - sa).normal()

    i1 = segment_sphere_isect(sa, sb, p, r)
    i2 = segment_sphere_isect(sa, sb, q, r)
    i3 = segment_cylinder_isect(sa, sb, p, q, r)

    dist = float('inf')
    closest_pt = None
    hit = False
    hitCylinder = False

    for i in [i1, i2, i3]:

        if i[0]:
            hit = True
            pt = i[1]

            if distance(sa, pt) < dist:
                closest_pt = pt

            dist = min(dist, distance(sa, pt))
            # draw_locator(i1[2], 'i1')

    return (hit, closest_pt, hitCylinder)


def checkCollision(cur_pos, pre_pos, capsuleLst, isRevert):
    # calculate collision with all the capsule in scene
    if isRevert:
        sa = cur_pos
        sb = pre_pos
    else:
        sb = cur_pos
        sa = pre_pos

    isHited = False
    closest_pt_dict = {}

    for obj in capsuleLst:
        objChildren = pm.listRelatives(obj, children=1, type='transform')
        p = objChildren[0].getTranslation(space='world')
        q = objChildren[1].getTranslation(space='world')
        r = obj.getAttr('scaleZ') * 1

        hit, closest_pt, hitCylinder = segment_capsule_isect(sa, sb, p, q, r)

        if hit:
            isHited = True
            closest_pt_dict[obj.name()] = [obj, closest_pt]
            # drawDebug_box(closest_pt)

    if isHited:
        pt_length = 9999
        closest_pt = None
        col_obj = None

        for pt in closest_pt_dict.keys():
            lLength = (closest_pt_dict[pt][1] - pre_pos).length()

            if lLength < pt_length:
                pt_length = lLength
                closest_pt = closest_pt_dict[pt][1]
                col_obj = closest_pt_dict[pt][0]

        # return col pt and col_body speed
        return closest_pt, col_obj, hitCylinder
    else:
        return None, None, None


def ckeckPointInTri(pos, pa, pb, pc):
    ra = math.acos(((pa - pos).normal()).dot((pb - pos).normal()))
    ra = dt.degrees(ra)
    rb = math.acos(((pb - pos).normal()).dot((pc - pos).normal()))
    rb = dt.degrees(rb)
    rc = math.acos(((pc - pos).normal()).dot((pa - pos).normal()))
    rc = dt.degrees(rc)

    return (abs(ra + rb + rc) > 359)


def getVertexPositions(obj):
    vertex_positions_list = []

    for vertex in obj.vtx:
        vertex_positions_list.append(vertex.getPosition(space='world'))

    return vertex_positions_list


def checkPlaneCollision(objPos, childPos, colPlane):

    v_coords = getVertexPositions(colPlane)

    collision_plane_matrix = pm.xform(colPlane, worldSpace=1, matrix=1, q=1)
    n = dt.Vector(collision_plane_matrix[4:7])    # Y axis direction of plane
    q = v_coords[1]
    d = n.dot(q)

    # get obj distance to plane
    toPlaneDistance = dist_to_plane(objPos, n, d)
    toPlaneDistance_child = dist_to_plane(childPos, n, d)

    # child projection position on plane
    projectPos_child = proj_pt_to_plane(childPos, n, d)

    inPlane = False

    if ckeckPointInTri(projectPos_child, v_coords[0], v_coords[1], v_coords[2]):
        inPlane = True
    elif ckeckPointInTri(projectPos_child, v_coords[3], v_coords[1], v_coords[2]):
        inPlane = True

    # bone above plane and bone child under plane and child project point on plane
    # means has collision with plane
    if (toPlaneDistance > 0) and (toPlaneDistance_child < 0) and inPlane:
        return projectPos_child
    else:
        return None
