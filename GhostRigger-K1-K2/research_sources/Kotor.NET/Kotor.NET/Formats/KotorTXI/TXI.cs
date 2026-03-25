namespace Kotor.NET.Formats.KotorTXI
{
    public class TXI
    {
    }

    public interface ITXIModifier
    {
        string RawString();
    }

    public class TXIMipmapModifier : ITXIModifier
    {
        public bool MipMapped { get; set; }

        public TXIMipmapModifier(bool mipmapped)
        {
            MipMapped = mipmapped;
        }

        public string RawString() => $"mipmap {Convert.ToInt16(MipMapped)}";
    }

    public enum BlendingType
    {
        Additive,
        Punchthrough,
    }
    public class TXIBlendingModifier : ITXIModifier
    {
        public BlendingType Type { get; set; }

        public TXIBlendingModifier(BlendingType type)
        {
            Type = type;
        }

        public string RawString() => $"blending {BlendingType.GetName(Type)!.ToLower()}";
    }

    public class TXIEnvironmentMappedModifier : ITXIModifier
    {
        public string Texture { get; set; }

        public TXIEnvironmentMappedModifier(string texture)
        {
            Texture = texture;
        }

        public string RawString() => $"envmaptexture {Texture}";
    }

    public class TXIBumpMapModifier : ITXIModifier
    {
        public bool BumpMapped { get; set; }

        public TXIBumpMapModifier(bool bumpmapped)
        {
            BumpMapped = bumpmapped;
        }

        public string RawString() => $"isbumpmap {Convert.ToInt32(BumpMapped)}";
    }
}
