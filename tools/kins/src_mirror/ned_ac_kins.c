/********************************************************************
* ned_ac_kins.c -- ned swivel-head (A about X, C about Z) tool-tip
* kinematics with an X gantry twin. NON-SWITCHABLE BY OPERATOR ORDER
* (2026-08-06: "never use switchkins. remove all possibility"): a
* runtime kins switch unhomes every joint, and this machine never
* switches -- identity sessions use trivkins inis, tool-tip sessions
* load this module, chosen at launch by run5.sh.
*
* Math lifted from the distro 5axiskins.c (Chris Radek, GPL2) with the
* BC-head yawed to an AC-head via azimuth-offset (90 => A tilts in YZ
* at C=0; the gantry is X-twin). Structure follows maxkins.c, the
* classic non-switchable pattern (KINS_NOT_SWITCHABLE).
*
* Pins:
*   ned_ac_kins.pivot-length    A-axis centerline -> TOOL TIP, mm.
*                               Fed at HAL load by run5's generated
*                               postgui (head_pivot.inc + tool length
*                               via the arm sum2). 250 = the unfed
*                               sentinel, deliberately implausible.
*   ned_ac_kins.azimuth-offset  deg added to C for the tilt azimuth.
*   ned_ac_kins.tilt-sign       +1/-1 physical A vs model.
*
* coordinates=XYZXAC (module param) maps letters to joints in order;
* the duplicate X carries the gantry pair (kins_util helpers).
********************************************************************/

#include "motion.h"
#include "hal.h"
#include "rtapi.h"
#include "rtapi_app.h"
#include "rtapi_math.h"
#include "rtapi_string.h"
#include "kinematics.h"
#include "posemath.h"

#define DEFAULT_PIVOT_LENGTH 250

static struct haldata {
    hal_float_t *pivot_length;
    hal_float_t *azimuth_offset;
    hal_float_t *tilt_sign;
} *haldata;

static char *coordinates = "XYZXAC";
RTAPI_MP_STRING(coordinates, "Axis letters mapped to joints, e.g. XYZXAC");

static int total_joints;

/* principal joint per letter (first occurrence in coordinates) */
static int JX = -1, JY = -1, JZ = -1, JA = -1, JB = -1, JC = -1;
static int JU = -1, JV = -1, JW = -1;

static PmCartesian s2r(double r, double t, double p) {
    PmCartesian c;
    t = TO_RAD*t; p = TO_RAD*p;
    c.x = r * sin(p) * cos(t);
    c.y = r * sin(p) * sin(t);
    c.z = r * cos(p);
    return c;
}

int kinematicsForward(const double *joints,
                      EmcPose * pos,
                      const KINEMATICS_FORWARD_FLAGS * fflags,
                      KINEMATICS_INVERSE_FLAGS * iflags)
{
    (void)fflags; (void)iflags;
    PmCartesian r = s2r(*(haldata->pivot_length),
                        joints[JC] + *(haldata->azimuth_offset),
                        180.0 - (*(haldata->tilt_sign) * joints[JA]));

    pos->tran.x = joints[JX] + r.x;
    pos->tran.y = joints[JY] + r.y;
    pos->tran.z = joints[JZ] + *(haldata->pivot_length) + r.z;
    pos->a      = joints[JA];
    pos->c      = joints[JC];
    pos->b = (JB != -1) ? joints[JB] : 0;
    pos->w = (JW != -1) ? joints[JW] : 0;
    pos->u = (JU != -1) ? joints[JU] : 0;
    pos->v = (JV != -1) ? joints[JV] : 0;
    return 0;
}

int kinematicsInverse(const EmcPose * pos,
                      double *joints,
                      const KINEMATICS_INVERSE_FLAGS * iflags,
                      KINEMATICS_FORWARD_FLAGS * fflags)
{
    (void)iflags; (void)fflags;
    PmCartesian r = s2r(*(haldata->pivot_length),
                        pos->c + *(haldata->azimuth_offset),
                        180.0 - (*(haldata->tilt_sign) * pos->a));
    EmcPose P;
    P.tran.x = pos->tran.x - r.x;
    P.tran.y = pos->tran.y - r.y;
    P.tran.z = pos->tran.z - *(haldata->pivot_length) - r.z;
    P.a = pos->a;
    P.c = pos->c;
    P.b = (JB != -1) ? pos->b : 0;
    P.w = (JW != -1) ? pos->w : 0;
    P.u = (JU != -1) ? pos->u : 0;
    P.v = (JV != -1) ? pos->v : 0;

    /* duplicate-letter support: the gantry X twin gets the same value */
    position_to_mapped_joints(total_joints, &P, joints);
    return 0;
}

KINEMATICS_TYPE kinematicsType(void)
{
    return KINEMATICS_BOTH;
}

KINS_NOT_SWITCHABLE
EXPORT_SYMBOL(kinematicsType);
EXPORT_SYMBOL(kinematicsForward);
EXPORT_SYMBOL(kinematicsInverse);
MODULE_LICENSE("GPL");

static int comp_id;

int rtapi_app_main(void)
{
    int res, jno;
    int axis_idx_for_jno[EMCMOT_MAX_JOINTS];

    total_joints = strlen(coordinates);
    if (total_joints > EMCMOT_MAX_JOINTS) return -1;

    if (map_coordinates_to_jnumbers(coordinates, EMCMOT_MAX_JOINTS,
                                    1,  /* allow duplicates: gantry X */
                                    axis_idx_for_jno)) return -1;

    for (jno = 0; jno < total_joints; jno++) {
        switch (axis_idx_for_jno[jno]) {
        case 0: if (JX < 0) JX = jno; break;
        case 1: if (JY < 0) JY = jno; break;
        case 2: if (JZ < 0) JZ = jno; break;
        case 3: if (JA < 0) JA = jno; break;
        case 4: if (JB < 0) JB = jno; break;
        case 5: if (JC < 0) JC = jno; break;
        case 6: if (JU < 0) JU = jno; break;
        case 7: if (JV < 0) JV = jno; break;
        case 8: if (JW < 0) JW = jno; break;
        }
    }
    if (JX < 0 || JY < 0 || JZ < 0 || JA < 0 || JC < 0) {
        rtapi_print_msg(RTAPI_MSG_ERR,
            "ned_ac_kins: coordinates=%s must carry X Y Z A C\n",
            coordinates);
        return -1;
    }

    comp_id = hal_init("ned_ac_kins");
    if (comp_id < 0) return comp_id;
    haldata = hal_malloc(sizeof(struct haldata));
    if (!haldata) { hal_exit(comp_id); return -1; }

    res  = hal_pin_float_newf(HAL_IN, &(haldata->pivot_length), comp_id,
                              "ned_ac_kins.pivot-length");
    res += hal_pin_float_newf(HAL_IN, &(haldata->azimuth_offset), comp_id,
                              "ned_ac_kins.azimuth-offset");
    res += hal_pin_float_newf(HAL_IN, &(haldata->tilt_sign), comp_id,
                              "ned_ac_kins.tilt-sign");
    if (res < 0) { hal_exit(comp_id); return res; }

    *(haldata->pivot_length)   = DEFAULT_PIVOT_LENGTH;
    *(haldata->azimuth_offset) = 90;
    *(haldata->tilt_sign)      = 1;

    rtapi_print("ned_ac_kins: NON-SWITCHABLE tool-tip kins, coordinates=%s "
                "(default pivot-length = %d until postgui feeds it)\n",
                coordinates, DEFAULT_PIVOT_LENGTH);
    hal_ready(comp_id);
    return 0;
}

void rtapi_app_exit(void) { hal_exit(comp_id); }
