using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Creature;
using Kotor.NET.Formats.KotorMDL;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class VertexArray
    {
        public uint VAO_ID { init; get; }
        public uint VBO_ID { get; }
        public uint EBO_ID { get; }

        public uint FaceCount { get; private set; }

        private GL _gl;

        public VertexArray(GL gl, IEnumerable<Vector3> points, IEnumerable<short> elements, IEnumerable<Vector3>? normals = null, IEnumerable<Vector2>? uv1s = null, IEnumerable<Vector2>? uv2s = null)
        {
            _gl = gl;

            VAO_ID = _gl.GenVertexArray();
            VBO_ID = _gl.GenBuffer();
            EBO_ID = _gl.GenBuffer();
        }

        public VertexArray(GL gl, byte[] vertexData, byte[] elementData, uint positionsOffset, uint normalsOffset, uint uv1Stride, uint uv2Stride, uint blockSize, int flags)
        {
            _gl = gl;

            VAO_ID = _gl.GenVertexArray();
            VBO_ID = _gl.GenBuffer();
            EBO_ID = _gl.GenBuffer();

            Assign(vertexData, elementData, positionsOffset, normalsOffset, uv1Stride, uv2Stride, blockSize, flags);
        }

        public VertexArray(GL gl, uint id, uint faceCount)
        {
            _gl = gl;

            VAO_ID = id;

            FaceCount = faceCount;
        }

        /// <summary>
        /// Initialize VertexArray with empty buffers.
        /// </summary>
        public VertexArray(GL gl)
        {
            _gl = gl;

            VAO_ID = _gl.GenVertexArray();
            VBO_ID = _gl.GenBuffer();
            EBO_ID = _gl.GenBuffer();
        }

        public unsafe void Draw()
        {
            _gl.BindVertexArray(VAO_ID);
            _gl.DrawElements(PrimitiveType.Triangles, FaceCount, DrawElementsType.UnsignedShort, (void*) 0);
        }

        public unsafe void Assign(IEnumerable<Vector3> points, IEnumerable<short> elements, IEnumerable<Vector3>? normals = null, IEnumerable<Vector2>? uv1s = null, IEnumerable<Vector2>? uv2s = null)
        {
            if (normals is not null && normals.Count() != points.Count())
                throw new NotImplementedException();
            if (uv1s is not null && uv1s.Count() != points.Count())
                throw new NotImplementedException();
            if (uv2s is not null && uv2s.Count() != points.Count())
                throw new NotImplementedException();

            var flags = 0;
            var blockSize = 0;
            var positionStride = 0;
            var normalStride = 0;
            var uv1Stride = 0;
            var uv2Stride = 0;

            if (points is not null)
            {
                flags |= 0x0001;
                positionStride = blockSize;
                blockSize += 12;
            }
            if (normals is not null)
            {
                //flags |= ;
                //normalStride =
                //blockStize += 12
            }
            if (uv1s is not null)
            {
                flags |= 0x0020;
                uv1Stride = blockSize;
                blockSize += 8;
            }
            if (uv2s is not null)
            {
                flags |= 0x0004;
                uv2Stride = blockSize;
                blockSize += 8;
            }

            var vertexData = new List<byte>();
            for (int i = 0; i < points.Count(); i++)
            {
                if (points is not null)
                {
                    vertexData.AddRange(BitConverter.GetBytes(points.ElementAt(i).X));
                    vertexData.AddRange(BitConverter.GetBytes(points.ElementAt(i).Y));
                    vertexData.AddRange(BitConverter.GetBytes(points.ElementAt(i).Z));
                }
                if (normals is not null)
                {
                    //vertexData.AddRange(BitConverter.GetBytes(normals.ElementAt(i).X));
                    //vertexData.AddRange(BitConverter.GetBytes(normals.ElementAt(i).Y));
                    //vertexData.AddRange(BitConverter.GetBytes(normals.ElementAt(i).Z));
                }
                if (uv1s is not null)
                {
                    vertexData.AddRange(BitConverter.GetBytes(uv1s.ElementAt(i).X));
                    vertexData.AddRange(BitConverter.GetBytes(uv1s.ElementAt(i).Y));
                }
                if (uv2s is not null)
                {
                    vertexData.AddRange(BitConverter.GetBytes(uv2s.ElementAt(i).X));
                    vertexData.AddRange(BitConverter.GetBytes(uv2s.ElementAt(i).Y));
                }
            }

            var elementData = elements.SelectMany(x => BitConverter.GetBytes(x));

            Assign(vertexData.ToArray(), elementData.ToArray(), (uint)positionStride, (uint)normalStride, (uint)uv1Stride, (uint)uv2Stride, (uint)blockSize, flags);
        }

        public unsafe void Assign(byte[] vertexData, byte[] elementData, uint positionsOffset, uint normalsOffset, uint uv1Stride, uint uv2Stride, uint blockSize, int flags)
        {
            _gl.BindVertexArray(VAO_ID);

            _gl.BindBuffer(BufferTargetARB.ArrayBuffer, VBO_ID);
            fixed (byte* buf = vertexData)
                _gl.BufferData(BufferTargetARB.ArrayBuffer, (nuint)vertexData.Length, buf, BufferUsageARB.StaticDraw);

            _gl.BindBuffer(BufferTargetARB.ElementArrayBuffer, EBO_ID);
            fixed (byte* buf = elementData)
                _gl.BufferData(BufferTargetARB.ElementArrayBuffer, (nuint)elementData.Length, buf, BufferUsageARB.StaticDraw);
            FaceCount = (uint)elementData.Count() / 2;

            if ((flags & 0x0001) > 0)
            {
                _gl.EnableVertexAttribArray(1);
                _gl.VertexAttribPointer(1, 3, VertexAttribPointerType.Float, false, blockSize, (void*)positionsOffset);
            }

            if ((flags & 0x0020) > 0)
            {
                _gl.EnableVertexAttribArray(3);
                _gl.VertexAttribPointer(3, 2, VertexAttribPointerType.Float, false, blockSize, (void*)uv1Stride);
            }

            if ((flags & 0x0004) > 0)
            {
                _gl.EnableVertexAttribArray(4);
                _gl.VertexAttribPointer(4, 2, VertexAttribPointerType.Float, false, blockSize, (void*)uv2Stride);
            }

            _gl.BindBuffer(BufferTargetARB.ArrayBuffer, 0);
            _gl.BindVertexArray(0);
        }
    }
}
