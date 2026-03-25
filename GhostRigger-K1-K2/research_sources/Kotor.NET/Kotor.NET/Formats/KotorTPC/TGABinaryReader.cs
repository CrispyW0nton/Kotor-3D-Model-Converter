using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.PortableExecutable;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorTLK;
using static Kotor.NET.Formats.KotorTPC.TGABinaryStructures;

namespace Kotor.NET.Formats.KotorTPC
{
    public class TGABinaryReader : IReader<TPC>
    {
        private BinaryReader _reader;
        private TPC? _tpc;

        public TGABinaryReader(string filepath)
        {
            var data = File.ReadAllBytes(filepath);
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TGABinaryReader(byte[] data)
        {
            _reader = new BinaryReader(new MemoryStream(data));
        }
        public TGABinaryReader(Stream stream)
        {
            _reader = new BinaryReader(stream);
        }

        public TPC Read()
        {
            var file = new TGA(_reader);

            bool flipY = (file.FileHeader.ImageDescriptor & 0b00100000) > 0;
            bool interleaving = (file.FileHeader.ImageDescriptor & 0b11000000) > 0;

            if (interleaving)
            {
                throw new Exception(); // TODO
            }

            TPCTextureFormat textureFormat;
            byte[] textureData;

            var dataTypeCode = (DataTypeCodes)file.FileHeader.DataTypeCode;
            if (dataTypeCode == DataTypeCodes.Uncompressed_ColourMapped)
            {
                throw new Exception(); // TODO
            }
            else if (dataTypeCode == DataTypeCodes.Uncompressed_RGB)
            {
                (textureData, textureFormat) = ReadUncompressed(file);
            }
            else if (dataTypeCode == DataTypeCodes.Uncompressed_Greyscale)
            {
                (textureData, textureFormat) = ReadUncompressed(file);
            }
            else if (dataTypeCode == DataTypeCodes.RLE_ColourMapped)
            {
                throw new Exception(); // TODO
            }
            else if (dataTypeCode == DataTypeCodes.RLE_RGB)
            {
                (textureData, textureFormat) = ReadRLE(file);
            }
            else if (dataTypeCode == DataTypeCodes.Compressed_Greyscale)
            {
                throw new Exception(); // TODO
            }
            else
            {
                throw new Exception(); // TODO
            }

            _tpc = new(file.FileHeader.Width, file.FileHeader.Height, textureFormat, textureData);
            return _tpc;
        }

        private (byte[], TPCTextureFormat) ReadUncompressed(TGA file)
        {
            if (file.FileHeader.BitsPerPixel == 24)
            {
                var data = (byte[])file.ImageData.Clone();
                for (int i = 0; i < file.ImageData.Length; i += 3)
                {
                    Array.Reverse(data, i, 3);
                }
                return (data, TPCTextureFormat.RGB);
            }
            else if (file.FileHeader.BitsPerPixel == 32)
            {
                var data = (byte[])file.ImageData.Clone();
                for (int i = 0; i < file.ImageData.Length; i += 4)
                {
                    Array.Reverse(data, i, 3);
                }
                return (data, TPCTextureFormat.RGBA);
            }
            else if (file.FileHeader.BitsPerPixel == 8)
            {
                var data = (byte[])file.ImageData.Clone();
                return (data, TPCTextureFormat.Greyscale);
            }
            else
            {
                throw new Exception(); // TODO
            }
        }

        private (byte[], TPCTextureFormat) ReadRLE(TGA file)
        {
            var tpcTextureFormat = (file.FileHeader.BitsPerPixel == 32) ? TPCTextureFormat.RGB : TPCTextureFormat.RGBA;
            var data = new List<byte>(); // TODO: initial size / convert to byte[]
            var n = 0;

            while (n < file.ImageData.Length)
            {
                var packet = file.ImageData[n];
                var isRawPacket = (packet & 0b10000000) > 0;
                var count = (packet & 0b01000000) + 1;

                if (isRawPacket)
                {
                    for (int i = 0; i < count; i ++)
                    {
                        data.AddRange(YoinkRGB(file.FileHeader.BitsPerPixel, file.ImageData, n + 1 + i));
                    }
                }
                else
                {
                    var pixel = YoinkRGB(file.FileHeader.BitsPerPixel, file.ImageData, n);

                    for (int i = 0; i < count; i++)
                    {
                        data.AddRange(pixel);
                    }
                }

                n += count;
            }
            return (data.ToArray(), tpcTextureFormat);
        }

        private byte[] YoinkRGB(byte bitsPerPixel, byte[] data, int skip)
        {
            if (bitsPerPixel == 32)
            {
                return data.Skip(skip).Take(3).Reverse().ToArray();
            }
            else if (bitsPerPixel == 24)
            {
                return data.Skip(skip).Take(3).Reverse().Concat(new byte[] {255}).ToArray();
            }
            else
            {
                throw new Exception(); // TODO
            }
        }
    }
}
