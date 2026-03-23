using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Geometry
{
    public class Vector2
    {
        public float X { get; set; }
        public float Y { get; set; }

        public Vector2()
        {

        }

        public Vector2(float x, float y)
        {
            X = x;
            Y = y;
        }
    }
}
