using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Common
{
    public interface IGFFCompiler
    {
        GFF CompileGFF();
    }
}
