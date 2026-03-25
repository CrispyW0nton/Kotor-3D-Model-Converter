using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Geometry
{
    public class Vector3
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }

        public Vector3()
        {

        }

        public Vector3(float x, float y, float z)
        {
            X = x;
            Y = y;
            Z = z;
        }

        public bool Equals(Vector3 other, float margin)
        {
            return X.Equals(other.X)
                && Y.Equals(other.Y)
                && Z.Equals(other.Z);
        }

        public static Vector3 operator +(Vector3 v1, Vector3 v2)
        {
            return new Vector3(v1.X + v2.X, v1.Y + v2.Y, v1.Z + v2.Z);
        }

        public static Vector3 operator -(Vector3 v1, Vector3 v2)
        {
            return new Vector3(v1.X - v2.X, v1.Y - v2.Y, v1.Z - v2.Z);
        }

        public static Vector3 operator /(Vector3 v1, int scale)
        {
            return new Vector3(v1.X / scale, v1.Y / scale, v1.Z / scale);
        }

        //public float this[int index]
        //{
        //    get
        //    {
        //        if (index == 0) return X;
        //        if (index == 1) return Y;
        //        if (index == 2) return Z;
        //        else throw new IndexOutOfRangeException();
        //    }
        //}

        public float this[Axis axis]
        {
            get
            {
                if (axis == Axis.X) return X;
                if (axis == Axis.Y) return Y;
                if (axis == Axis.Z) return Z;
                else throw new IndexOutOfRangeException();
            }
        }
    }

    public enum Axis
    {
        X,
        Y,
        Z,
        W,
    }
}
