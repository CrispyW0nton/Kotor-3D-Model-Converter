using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorMDL;
using Kotor.NET.Formats.KotorTPC;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class Texture
    {
        public uint ID { get; set; }

        private GL _gl { get; set; }

        public unsafe Texture(GL gl, TPC tpc)
        {
            _gl = gl;

            var mipmap = tpc.GetMipmap(0);

            ID = gl.GenTexture();
            gl.BindTexture(GLEnum.Texture2D, ID);

            if (tpc.Format == TPCTextureFormat.DXT1)
            {
                fixed (byte* buf = mipmap.Data)
                    gl.CompressedTexImage2D(GLEnum.Texture2D, 0, InternalFormat.CompressedRgbS3TCDxt1Ext, (uint)tpc.Width, (uint)tpc.Height, 0, (uint)mipmap.Size, buf);
            }
            else if (tpc.Format == TPCTextureFormat.DXT5)
            {
                fixed (byte* buf = mipmap.Data)
                    gl.CompressedTexImage2D(GLEnum.Texture2D, 0, InternalFormat.CompressedRgbaS3TCDxt5Ext, (uint)tpc.Width, (uint)tpc.Height, 0, (uint)mipmap.Size, buf);
            }
            else if (tpc.Format == TPCTextureFormat.RGB)
            {
                fixed (byte* buf = mipmap.Data)
                    gl.TexImage2D(GLEnum.Texture2D, 0, InternalFormat.Rgb, (uint)mipmap.Width, (uint)mipmap.Height, 0, GLEnum.Rgb, PixelType.UnsignedByte, buf);
            }
            else if (tpc.Format == TPCTextureFormat.RGBA)
            {
                fixed (byte* buf = mipmap.Data)
                    gl.TexImage2D(GLEnum.Texture2D, 0, InternalFormat.Rgba, (uint)mipmap.Width, (uint)mipmap.Height, 0, GLEnum.Rgba, PixelType.UnsignedByte, buf);
            }

            var textureWrapSFilter = (int)GLEnum.Repeat;
            gl.TexParameterI(TextureTarget.Texture2D, TextureParameterName.TextureWrapS,  textureWrapSFilter);
            var textureWrapTFilter = (int)GLEnum.Repeat;
            gl.TexParameterI(TextureTarget.Texture2D, TextureParameterName.TextureWrapT, textureWrapTFilter);
            var textureMinFilter = (int)GLEnum.NearestMipmapLinear;
            gl.TexParameterI(TextureTarget.Texture2D, TextureParameterName.TextureMinFilter, textureMinFilter);
            var textureMagFilter = (int)GLEnum.Linear;
            gl.TexParameterI(TextureTarget.Texture2D, TextureParameterName.TextureMagFilter, textureMagFilter);

            gl.GenerateMipmap(TextureTarget.Texture2D);
        }

        public void Use()
        {
            _gl.BindTexture(TextureTarget.Texture2D, ID);
        }
    }
}
