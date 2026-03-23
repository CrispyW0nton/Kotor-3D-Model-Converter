using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Data
{
    public class ResRef
    {
        private string _value = "";

        public ResRef()
        {

        }

        public ResRef(string value)
        {
            Set(value);
        }

        public string Get()
        {
            return _value;
        }

        public void Set(string value)
        {
            if (value.Length > 16)
            {
                throw new ArgumentException("Length exceeds 16");
            }

            _value = value.Replace("\0", "");
        }

        public override string ToString()
        {
            return _value;
        }

        public static bool operator ==(ResRef left, ResRef right)
        {
            return left._value == right._value;
        }
        public static bool operator !=(ResRef left, ResRef right)
        {
            return left._value != right._value;
        }
        public override bool Equals(object? obj)
        {
            var resref = obj as ResRef;

            if (resref is null)
            {
                return false;
            }

            return _value == resref._value;
        }
        public override int GetHashCode()
        {
            return _value.GetHashCode();
        }

        public static implicit operator ResRef(string value)
        {
            return new ResRef(value);
        }
    }
}
