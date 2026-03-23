using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Graphics.Extensions
{
    public static class Matrix4x4Extensions
    {
        public static ReadOnlySpan<float> ToFloatSpan(this Matrix4x4 m)
        {
            return new Span<float>(new float[]
            {
                m.M11, m.M12, m.M13, m.M14,
                m.M21, m.M22, m.M23, m.M24,
                m.M31, m.M32, m.M33, m.M34,
                m.M41, m.M42, m.M43, m.M44,
            });
        }
    }
}
