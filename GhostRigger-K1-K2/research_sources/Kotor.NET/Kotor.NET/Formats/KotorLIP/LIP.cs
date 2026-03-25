using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.KotorLIP
{
    public class LIP
    {
        public float Length { get; set; }
        public List<LIPKeyFrame> KeyFrames { get; set; }
    }

    public enum MouthShape
    {
        Neutral,
        EE_IH_IY,
        EH_ER_EY,
        AA_AE_AH,
        OW_OY,
        UH_UW_W,
        D_DH_S_Y_Z,
        CH_JH_SH_ZH,
        F_V,
        G_HH_K_NG,
        T_TH,
        B_M_P,
        L_N,
        R,
        AW_AY,
        AO
    }

    public class LIPKeyFrame
    {
        public float Time { get; set; }
        public MouthShape Shape { get; set; }
    }
}
