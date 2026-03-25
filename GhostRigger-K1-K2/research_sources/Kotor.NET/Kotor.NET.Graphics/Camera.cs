using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Reflection.Metadata;
using System.Text;
using System.Threading.Tasks;
using Silk.NET.Maths;

namespace Kotor.NET.Graphics
{
    public class Camera
    {
        public float TargetX { get; set; } = 3.0f;
        public float TargetY { get; set; } = 3.0f;
        public float TargetZ { get; set; } = 0.5f;

        public float MouseX { get; set; }
        public float MouseY { get; set; }
        public float MouseZ { get; set; }

        public uint Width { get; set; } = 400;
        public uint Height { get; set; } = 400;
        public float Distance
        {
            get => _distance;
            set => _distance = MathF.Max(1, value);
        }
        public float Pitch
        {
            get => _pitch;
            set => _pitch = (float)Math.Clamp(value, Math.PI/2+0.0001, Math.PI-0.0001);
        }
        public float Yaw { get; set; }
        public float Near { get; set; } = 0.001f;
        public float Far { get; set; } = 1000;
        public float FieldOfView { get; set; }
        public float AspectRatio => (float)Width / (float)Height;

        private float _pitch = (float)(Math.PI / 4);
        private float _distance = 4;

        public Matrix4x4 GetView()
        {
            var target = new Vector3(TargetX, TargetY, TargetZ);

            var up = new Vector3(0, 0, 1);
            var pitch = new Vector3(1, 0, 0);

            var x = TargetX + MathF.Cos(Yaw) * MathF.Cos((float)(Pitch - Math.PI / 2)) * Distance; 
            var y = TargetY + MathF.Sin(Yaw) * MathF.Cos((float)(Pitch - Math.PI / 2)) * Distance;
            var z = TargetZ + MathF.Sin((float)(Pitch - Math.PI /2)) * Distance;

            var cam = new Vector3(x, y, z);

            return Matrix4x4.CreateLookAt(cam, target, up);
        }

        public Matrix4x4 GetProjection()
        {
            return Matrix4x4.CreatePerspectiveFieldOfView(1.39f, AspectRatio, Near, Far);
        }

        public Vector3 GetDirection()
        {
            return new(
                MathF.Cos(Yaw) * MathF.Cos((float)(Pitch - Math.PI / 2)) * Distance,
                MathF.Sin(Yaw) * MathF.Cos((float)(Pitch - Math.PI / 2)) * Distance,
                TargetZ + MathF.Sin((float)(Pitch - Math.PI / 2)) * Distance
            );
        }
    }
}
