using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics.Extensions;
using Silk.NET.Maths;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class Shader
    {
        public uint ProgramID { init; get; }
        public uint VertexShaderID { init; get; }
        public uint FragmentShaderID { init; get; }

        private GL _gl;

        public Shader(GL gl, Stream vertexShaderStream, Stream fragmentShaderStream)
        {
            _gl = gl;

            VertexShaderID = _gl.CreateShader(ShaderType.VertexShader);
            FragmentShaderID = _gl.CreateShader(ShaderType.FragmentShader);
            ProgramID = _gl.CreateProgram();

            var vertexStreamReader = new StreamReader(vertexShaderStream);
            var vertexShaderSource = vertexStreamReader.ReadToEnd();

            var fragmentStreamReader = new StreamReader(fragmentShaderStream);
            var fragmentShaderSource = fragmentStreamReader.ReadToEnd();

            InitializeShader(vertexShaderSource, fragmentShaderSource);
        }

        public Shader(GL gl, string vertexShaderSource, string fragmentShaderSource)
        {
            _gl = gl;

            VertexShaderID = _gl.CreateShader(ShaderType.VertexShader);
            FragmentShaderID = _gl.CreateShader(ShaderType.FragmentShader);
            ProgramID = _gl.CreateProgram();

            InitializeShader(vertexShaderSource, fragmentShaderSource);
        }

        ~Shader()
        {
            //_gl.DetachShader(program, vertexShader);
            //_gl.DetachShader(program, fragmentShader);
            //_gl.DeleteShader(vertexShader);
            //_gl.DeleteShader(fragmentShader);
        }

        public void Use()
        {
            _gl.UseProgram(ProgramID);
        }

        public int GetUniformLocation(string name)
        {
            return _gl.GetUniformLocation(ProgramID, name);
        }

        public void SetUniformVector3(string name, Vector3 value)
        {
            var location = GetUniformLocation(name);
            _gl.Uniform3(location, value);
        }

        public void SetUniformVector4(string name, Vector4 value)
        {
            var location = GetUniformLocation(name);
            _gl.Uniform4(location, value);
        }

        public void SetUniformMatrix4x4(string name, Matrix4x4 matrix)
        {
            var location = GetUniformLocation(name);
            var value = matrix.ToFloatSpan();
            _gl.UniformMatrix4(location, false, value);
        }

        private void InitializeShader(string vertexShaderSource, string fragmentShaderSource)
        {
            int success;

            _gl.ShaderSource(VertexShaderID, vertexShaderSource);
            _gl.CompileShader(VertexShaderID);
            _gl.GetShader(VertexShaderID, GLEnum.CompileStatus, out success);
            if (success == 0)
            {
                string infoLog = _gl.GetShaderInfoLog(VertexShaderID);
                throw new Exception(infoLog);
            }

            _gl.ShaderSource(FragmentShaderID, fragmentShaderSource);
            _gl.CompileShader(FragmentShaderID);
            _gl.GetShader(FragmentShaderID, GLEnum.CompileStatus, out success);
            if (success == 0)
            {
                string infoLog = _gl.GetShaderInfoLog(FragmentShaderID);
                throw new Exception(infoLog);
            }

            _gl.AttachShader(ProgramID, VertexShaderID);
            _gl.AttachShader(ProgramID, FragmentShaderID);
            _gl.LinkProgram(ProgramID);
            _gl.GetProgramInfoLog(ProgramID, out string info);
            if (info != "")
            {
                string infoLog = _gl.GetShaderInfoLog(ProgramID);
                throw new Exception(infoLog);
            }
        }
    }
}
