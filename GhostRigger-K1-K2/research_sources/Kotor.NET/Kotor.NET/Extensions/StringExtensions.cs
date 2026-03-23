using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Extensions
{
    public static class StringExtensions
    {
        public static string Truncate(this string value, int length)
        {
            var count = (value.Length < length) ? value.Length : length;
            return new string(value.ToList().GetRange(0, count).ToArray());
        }

        public static string Resize(this string value, int length, char padding = '\0')
        {
            return value.Truncate(32).PadRight(length, padding);
        }

        public static bool EqualsIgnoreCase(this string value1, string value2)
        {
            return StringComparer.CurrentCultureIgnoreCase.Equals(value1, value2);
        }

        public static bool IsInt8(this string value)
        {
            return SByte.TryParse(value, out _);
        }
        public static bool IsUInt8(this string value)
        {
            return Byte.TryParse(value, out _);
        }
        public static bool IsInt16(this string value)
        {
            return Int16.TryParse(value, out _);
        }
        public static bool IsUInt16(this string value)
        {
            return UInt16.TryParse(value, out _);
        }
        public static bool IsInt32(this string value)
        {
            return Int32.TryParse(value, out _);
        }
        public static bool IsUInt32(this string value)
        {
            return UInt32.TryParse(value, out _);
        }
        public static bool IsInt64(this string value)
        {
            return Int64.TryParse(value, out _);
        }
        public static bool IsUInt64(this string value)
        {
            return UInt64.TryParse(value, out _);
        }
        public static bool IsSingle(this string value)
        {
            return Single.TryParse(value, out _);
        }
        public static bool IsDouble(this string value)
        {
            return Double.TryParse(value, out _);
        }
    }
}
