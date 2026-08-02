// ned_homing_params -- send EMC_JOINT_SET_HOMING_PARAMS (NML type 112) to a
// RUNNING LinuxCNC. This is the runtime homing override python never wrapped
// (operator was right, 2026-08-02): search/latch velocities set to 0 turn a
// home command into a genuine home-in-place ("declare"), restorable after.
//
// Usage:
//   ned_homing_params <joint> <home> <offset> <final_vel> <search_vel>
//                     <latch_vel> <use_index> <ignore_limits> <sequence>
//   (volatile/is_shared/locking_indexer/absolute_encoder/enc_no_reset = 0)
//
// Build (tools/live):
//   g++ -O2 -o ned_homing_params ned_homing_params.cc \
//       -I/usr/include/linuxcnc -llinuxcnc -lnml -llinuxcncini
#include <stdio.h>
#include <stdlib.h>
#include "rcs.hh"
#include "emc.hh"
#include "emc_nml.hh"

int main(int argc, char **argv)
{
    if (argc != 10) {
        fprintf(stderr, "usage: %s joint home offset final_vel search_vel "
                        "latch_vel use_index ignore_limits sequence\n", argv[0]);
        return 2;
    }
    RCS_CMD_CHANNEL cmd(emcFormat, "emcCommand", "xemc",
                        "/usr/share/linuxcnc/linuxcnc.nml");
    if (!cmd.valid()) {
        fprintf(stderr, "ned_homing_params: emcCommand channel invalid "
                        "(is LinuxCNC running?)\n");
        return 1;
    }
    EMC_JOINT_SET_HOMING_PARAMS m;
    m.joint = atoi(argv[1]);
    m.home = atof(argv[2]);
    m.offset = atof(argv[3]);
    m.home_final_vel = atof(argv[4]);
    m.search_vel = atof(argv[5]);
    m.latch_vel = atof(argv[6]);
    m.use_index = atoi(argv[7]);
    m.encoder_does_not_reset = 0;
    m.ignore_limits = atoi(argv[8]);
    m.is_shared = 0;
    m.home_sequence = atoi(argv[9]);
    m.volatile_home = 0;
    m.locking_indexer = 0;
    m.absolute_encoder = 0;
    if (cmd.write(&m)) {
        fprintf(stderr, "ned_homing_params: NML write failed\n");
        return 1;
    }
    return 0;
}
