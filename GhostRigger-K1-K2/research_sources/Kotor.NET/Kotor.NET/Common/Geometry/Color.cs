using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Geometry
{
    public class Color
    {
        public float Red { get; set; }
        public float Green { get; set; }
        public float Blue { get; set; }
        public float Alpha { get; set; }

        public Color()
        {

        }

        public Color(float red, float green, float blue, float alpha)
        {
            Red = red;
            Blue = blue;
            Green = green;
            Alpha = alpha;
        }
    }

    public enum ColorEncoding
    {
        RGB_Floats,
    }
}
