using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Extensions
{
    public static class FloatExtensions
    {
        public static bool IsEqualTo(this float a, double b, double margin)
        {
            return Math.Abs(a - b) < margin;
        }

        public static bool IsEqualTo(this float a, float b)
        {
            return Math.Abs(a - b) < float.Epsilon;
        }
    }
}
